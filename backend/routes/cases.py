from datetime import timedelta
import difflib
import json
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_file

import ai
from files import store, validate_uploads
from models import Attachment, Case, Message, Notification, ReportHistory, TriageSession, User, db, now
from pdf import report_pdf
from security import ApiError, audit, auth, decrypt, error, throttle
from serializers import access_log, case_detail, case_summary, message_data, profile_complete, snapshot
import triage
from workflow import (FOLLOWUP_DAYS, OPEN_STATUSES, REPORT_TEXT_FIELDS, URGENCY_LABELS, VISIT_LABELS, allowed_actions,
                      higher_urgency, local_date, notify, record, require, reset_deadline)

bp = Blueprint('cases', __name__)
CONSENT_VERSION = '2026-10'
TRIAGE_TTL = timedelta(hours=6)


# ------------------------------------------------------------------ helpers

def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def load_case(case_id, lock=False):
    query = db.select(Case).where(Case.id == case_id)
    if lock:
        query = query.with_for_update()
    case = db.session.execute(query).scalar_one_or_none()
    if not case or g.user.id not in (case.patient_id, case.doctor_id):
        raise ApiError('病例不存在或无权访问', 404)
    return case


def reason_from(data, field='reason', required=True, label='原因'):
    value = data.get(field, '')
    if not isinstance(value, str) or len(value.strip()) > 500:
        raise ApiError(f'{label}最多 500 字')
    value = value.strip()
    if required and len(value) < 4:
        raise ApiError(f'请填写{label}（至少 4 个字）')
    return value or None


def target_doctor(doctor_id, exclude=None):
    doctor = db.session.get(User, doctor_id) if isinstance(doctor_id, int) else None
    if not doctor or doctor.role != 'doctor':
        raise ApiError('请选择有效医生')
    if not doctor.accepting:
        raise ApiError(f'{doctor.name}目前暂停接诊，请选择其他医生')
    if exclude and doctor.id == exclude:
        raise ApiError('请选择另一位医生')
    return doctor


def check_version(case, data):
    if data.get('version') != case.report_version:
        raise ApiError('报告已在其他地方更新，请刷新后再操作', 409)


def clean_report(data, complete):
    if not isinstance(data, dict):
        raise ApiError('报告格式无效')
    report = {}
    for field in REPORT_TEXT_FIELDS:
        value = data.get(field) or ''
        if not isinstance(value, str) or len(value) > 15000:
            raise ApiError('报告格式无效，单项内容最多 15000 字')
        report[field] = value.strip()
    visit, days = data.get('visit'), data.get('followup_days')
    if visit is not None and visit not in VISIT_LABELS:
        raise ApiError('线下就诊建议无效')
    if days is not None and (isinstance(days, bool) or days not in FOLLOWUP_DAYS):
        raise ApiError('随访安排无效')
    report.update(visit=visit, followup_days=days)
    if complete:
        if not all(report[f] for f in REPORT_TEXT_FIELDS):
            raise ApiError('请完成全部四项报告内容')
        if visit is None:
            raise ApiError('请选择线下就诊建议')
        if days is None:
            raise ApiError('请选择随访安排')
    return report


def save_draft(case, report, action, reason=None):
    case.draft = report
    case.report_version += 1
    db.session.add(ReportHistory(case_id=case.id, doctor_id=g.user.id, version=case.report_version,
                                 action=action, content=report, reason=reason))


def edit_ratio(original, final):
    if not original:
        return None
    joined = lambda report: '\n'.join(report.get(f) or '' for f in REPORT_TEXT_FIELDS)
    return round(1 - difflib.SequenceMatcher(None, joined(original), joined(final), autojunk=False).ratio(), 3)


def detail(case):
    return jsonify(case_detail(case, g.user))


def mark_read(case):
    stamp = now()
    if g.user.role == 'patient':
        case.patient_read_at = stamp
    else:
        case.doctor_read_at = stamp
    db.session.execute(db.update(Notification).where(
        Notification.user_id == g.user.id, Notification.case_id == case.id,
        Notification.kind == 'message', Notification.read_at.is_(None)).values(read_at=stamp))


def form_answers():
    raw = request.form.get('answers', '[]')
    try:
        answers = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError('预问诊回答格式无效') from exc
    if not isinstance(answers, list) or len(answers) > 5:
        raise ApiError('预问诊回答格式无效')
    cleaned = []
    for item in answers:
        if not isinstance(item, dict) or not isinstance(item.get('q'), str) or not isinstance(item.get('a', ''), str):
            raise ApiError('预问诊回答格式无效')
        if len(item['q']) > 100 or len(item.get('a', '')) > 1000:
            raise ApiError('每个回答最多 1000 字')
        if item.get('a', '').strip():
            cleaned.append({'q': item['q'].strip(), 'a': item['a'].strip()})
    return cleaned


def validate_text(title, description, duration):
    if not 2 <= len(title) <= 100:
        raise ApiError('病情标题为 2 至 100 字')
    if not 10 <= len(description) <= 15000:
        raise ApiError('症状描述为 10 至 15000 字，请尽量写清楚开始时间和变化')
    if len(duration) > 100:
        raise ApiError('持续时间最多 100 字')


# ------------------------------------------------------------------ triage

@bp.post('/triage')
@auth('patient')
def pre_consult():
    data = body()
    title, description, duration = (str(data.get(k) or '').strip() for k in ('title', 'description', 'duration'))
    validate_text(title, description, duration)
    rules = triage.assess(title, description, duration)
    result = {'rules': rules, 'ai': None}
    ai_error = None
    if data.get('use_ai') is True:
        throttle(f'triage:{g.user.id}', 12, 3600, 'AI 预问诊次数过多，请稍后再试')
        if not ai.configured():
            ai_error = 'AI 预问诊暂不可用，可直接继续填写'
        else:
            try:
                result['ai'] = ai.pre_consult(snapshot(g.user), title, description, duration)
                audit('ai_pre_consult', model=result['ai']['model'])
            except ai.AIError as exc:
                ai_error = f'{exc}，可直接继续填写'
    session = TriageSession(user_id=g.user.id, fingerprint=triage.fingerprint(title, description, duration), result=result)
    db.session.add(session)
    db.session.commit()
    ai_part = result['ai']
    return jsonify({'id': session.id, 'level': higher_urgency(rules['level'], ai_part and ai_part['level']),
                    'flags': rules['flags'], 'ai': ai_part and {k: v for k, v in ai_part.items() if k != 'doctor_summary'},
                    'ai_error': ai_error})


# ------------------------------------------------------------- list / create

@bp.get('/cases')
@auth()
def list_cases():
    column = Case.patient_id if g.user.role == 'patient' else Case.doctor_id
    records = db.session.execute(db.select(Case).where(column == g.user.id).order_by(Case.created_at.desc())).scalars()
    return jsonify([case_summary(case, g.user) for case in records])


@bp.post('/cases')
@auth('patient')
def create_case():
    if not profile_complete(g.user):
        return error('请先完善健康档案（身份证号、过敏史、当前用药）', 422)
    throttle(f'submit:{g.user.id}', 10, 3600, '提交过于频繁，请稍后再试')
    form = request.form
    title, description, duration = (form.get(k, '').strip() for k in ('title', 'description', 'duration'))
    validate_text(title, description, duration)
    if form.get('consent_share') != 'true':
        return error('提交前请同意将健康资料提供给所选医生')
    consent_ai = form.get('consent_ai') == 'true'
    answers = form_answers()
    parent = None
    if form.get('parent_id'):
        parent = db.session.get(Case, form.get('parent_id', type=int) or 0)
        if not parent or parent.patient_id != g.user.id or parent.status != 'completed':
            return error('只能基于已完成的病例发起复诊')
        if any(child.status in OPEN_STATUSES for child in parent.children):
            return error('该病例已有进行中的复诊')
    doctor = target_doctor(form.get('doctor_id', type=int))
    validated = validate_uploads(request.files.getlist('attachments'))

    assessment = triage.assess(title, description, duration, answers)
    ai_part = None
    session = db.session.get(TriageSession, form.get('triage_id', type=int) or 0)
    if (consent_ai and session and session.user_id == g.user.id and session.created_at
            and session.fingerprint == triage.fingerprint(title, description, duration)
            and now() - session.created_at < TRIAGE_TTL):
        ai_part = session.result.get('ai')
    urgency = higher_urgency(assessment['level'], ai_part and ai_part.get('level'))

    case = Case(patient_id=g.user.id, doctor_id=doctor.id, kind='followup' if parent else 'initial',
                parent_id=parent.id if parent else None, title=title, description=description, duration=duration,
                urgency=urgency, triage={'level': assessment['level'], 'flags': assessment['flags'], 'ai': ai_part},
                answers=answers, profile_snapshot=snapshot(g.user), consent_ai=consent_ai, consent_at=now(),
                consent_version=CONSENT_VERSION, status='pending')
    reset_deadline(case)
    written = []
    try:
        db.session.add(case)
        db.session.flush()
        store(validated, case.id, g.user.id, written=written)
        record(case, 'submitted', f'{"复诊" if parent else "病例"}已提交，等待{doctor.name}接诊', g.user)
        prefix = '【紧急】' if urgency == 'emergency' else ''
        notify(doctor.id, case, 'new_case', f'{prefix}新{"复诊" if parent else "病例"}：{title}',
               f'{case.profile_snapshot["name"]}，紧急程度：{URGENCY_LABELS[urgency]}')
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return detail(case), 201


@bp.get('/cases/<int:case_id>')
@auth()
def get_case(case_id):
    case = load_case(case_id)
    if g.user.role == 'doctor':
        audit('case_viewed', case.id, dedupe_minutes=30)
        db.session.commit()
    return detail(case)


# ------------------------------------------------------------ doctor actions

@bp.post('/cases/<int:case_id>/accept')
@auth('doctor')
def accept(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'accept')
    case.status, case.accepted_at = 'processing', now()
    record(case, 'accepted', f'{g.user.name}已接诊，正在评估', g.user)
    notify(case.patient_id, case, 'accepted', '医生已接诊', f'{g.user.name}正在评估：{case.title}')
    db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/decline')
@auth('doctor')
def decline(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'decline')
    reason = reason_from(body(), label='退回原因')
    case.status, case.status_reason = 'declined', reason
    record(case, 'declined', f'{g.user.name}退回了病例', g.user, reason)
    notify(case.patient_id, case, 'declined', '病例被退回，可改投其他医生', reason)
    db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/transfer')
@auth('doctor')
def transfer(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'transfer')
    data = body()
    doctor = target_doctor(data.get('doctor_id'), exclude=case.doctor_id)
    reason = reason_from(data, label='转诊原因')
    case.doctor_id, case.status, case.status_reason = doctor.id, 'pending', reason
    case.accepted_at = case.doctor_read_at = None
    case.draft, case.ai_draft, case.ai_model, case.ai_generated_at = None, None, None, None
    reset_deadline(case)
    record(case, 'transferred', f'{g.user.name}将病例转给{doctor.name}（{doctor.department}）', g.user, reason)
    notify(case.patient_id, case, 'transferred', f'病例已转给{doctor.name}', reason)
    notify(doctor.id, case, 'new_case', f'转诊病例：{case.title}', f'{g.user.name}转诊：{reason}')
    db.session.commit()
    return jsonify({'transferred': True, 'doctor': doctor.name})


@bp.post('/cases/<int:case_id>/urgency')
@auth('doctor')
def set_urgency(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'set_urgency')
    level = body().get('urgency')
    if level not in URGENCY_LABELS:
        return error('紧急程度无效')
    if level != case.urgency:
        case.urgency = level
        if case.status == 'pending':
            reset_deadline(case)
        record(case, 'urgency', f'{g.user.name}将紧急程度调整为“{URGENCY_LABELS[level]}”', g.user)
        db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/request-info')
@auth('doctor')
def request_info(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'request_info')
    text = body().get('message', '')
    if not isinstance(text, str) or not 5 <= len(text.strip()) <= 2000:
        return error('请写明需要患者补充的内容（5 至 2000 字）')
    db.session.add(Message(case_id=case.id, sender_id=g.user.id, kind='info_request', body=text.strip()))
    case.status = 'awaiting_info'
    record(case, 'info_requested', f'{g.user.name}请患者补充资料', g.user, text.strip())
    notify(case.patient_id, case, 'info_requested', '医生请你补充资料', text.strip())
    db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/resume')
@auth('doctor')
def resume(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'resume')
    case.status = 'processing'
    record(case, 'resumed', f'{g.user.name}结束等待，继续评估', g.user)
    notify(case.patient_id, case, 'resumed', '医生已继续评估', '无需再补充资料')
    db.session.commit()
    return detail(case)


@bp.put('/cases/<int:case_id>/draft')
@auth('doctor')
def update_draft(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'edit_draft')
    data = body()
    check_version(case, data)
    save_draft(case, clean_report(data.get('report'), complete=False), 'saved')
    db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/ai')
@auth('doctor')
def ai_draft(case_id):
    case = load_case(case_id)
    require(case, g.user, 'ai_draft')
    version = case.report_version
    check_version(case, body())
    throttle(f'ai-draft:{g.user.id}', 30, 3600, 'AI 草稿生成次数过多，请稍后再试')
    conversation = [{'from': '医生' if m.sender.role == 'doctor' else '患者', 'text': m.body[:2000]}
                    for m in db.session.execute(db.select(Message).where(Message.case_id == case.id)
                                                .order_by(Message.id)).scalars()]
    try:
        content, model = ai.draft_report(case, conversation)
    except ai.AIError as exc:
        return error(str(exc), 502)
    db.session.rollback()
    case = load_case(case_id, lock=True)
    if 'ai_draft' not in allowed_actions(case, g.user) or case.report_version != version:
        return error('报告在生成期间已被修改，AI 草稿未覆盖现有内容，请重试', 409)
    save_draft(case, content, 'ai_generated')
    case.ai_draft, case.ai_model, case.ai_generated_at = content, model, now()
    audit('ai_draft', case.id, model=model)
    db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/publish')
@auth('doctor')
def publish(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'publish')
    data = body()
    check_version(case, data)
    if data.get('confirmed') is not True:
        return error('请确认已逐项审核报告内容')
    report = clean_report(data.get('report'), complete=True)
    save_draft(case, report, 'published')
    case.report, case.status, case.status_reason = report, 'completed', None
    case.published_at, case.published_version = now(), 1
    case.followup_due = local_date() + timedelta(days=report['followup_days']) if report['followup_days'] else None
    case.ai_edit_ratio = edit_ratio(case.ai_draft, report)
    record(case, 'published', f'{g.user.name}审核并发布了诊疗报告', g.user)
    notify(case.patient_id, case, 'published', '诊疗报告已发布', case.title)
    db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/amend')
@auth('doctor')
def amend(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'amend')
    data = body()
    if data.get('published_version') != case.published_version:
        return error('报告已被更正过，请刷新后再操作', 409)
    if data.get('confirmed') is not True:
        return error('请确认已审核更正后的报告')
    reason = reason_from(data, label='更正原因')
    report = clean_report(data.get('report'), complete=True)
    if report == {k: case.report.get(k) for k in report}:
        return error('报告内容没有变化')
    previous_days = case.report.get('followup_days')
    save_draft(case, report, 'amended', reason)
    case.report, case.status_reason = report, reason
    case.published_version += 1
    case.amended_at = now()
    if report['followup_days'] != previous_days:
        case.followup_due = local_date() + timedelta(days=report['followup_days']) if report['followup_days'] else None
    record(case, 'amended', f'{g.user.name}更正了诊疗报告（第 {case.published_version} 版）', g.user, reason)
    notify(case.patient_id, case, 'amended', '诊疗报告已更正', reason)
    db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/reveal-id')
@auth('doctor')
def reveal_id(case_id):
    case = load_case(case_id)
    audit('national_id_revealed', case.id)
    db.session.commit()
    return jsonify({'national_id': decrypt(case.profile_snapshot.get('national_id_encrypted', ''))})


@bp.get('/cases/<int:case_id>/report/history')
@auth('doctor')
def report_history(case_id):
    load_case(case_id)
    rows = db.session.execute(db.select(ReportHistory).where(ReportHistory.case_id == case_id)
                              .order_by(ReportHistory.version.desc())).scalars()
    return jsonify([{'version': r.version, 'action': r.action, 'content': r.content, 'reason': r.reason,
                     'created_at': r.created_at.isoformat() if r.created_at else None} for r in rows])


# ----------------------------------------------------------- patient actions

@bp.post('/cases/<int:case_id>/supplement')
@auth('patient')
def supplement(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'supplement')
    text = request.form.get('body', '').strip()
    validated = validate_uploads(request.files.getlist('attachments'), existing=len(case.attachments))
    if len(text) > 2000 or (not text and not validated):
        return error('请填写补充说明或上传资料（说明最多 2000 字）')
    written = []
    try:
        message = Message(case_id=case.id, sender_id=g.user.id, kind='supplement',
                          body=text or f'补充了 {len(validated)} 个附件')
        db.session.add(message)
        db.session.flush()
        store(validated, case.id, g.user.id, message.id, written)
        case.status = 'processing'
        record(case, 'supplemented', '患者已补充资料，等待医生继续评估', g.user)
        notify(case.doctor_id, case, 'supplemented', f'患者已补充资料：{case.title}', text[:100])
        mark_read(case)
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    db.session.expire(case, ['attachments'])
    return detail(case)


@bp.post('/cases/<int:case_id>/reassign')
@auth('patient')
def reassign(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'reassign')
    doctor = target_doctor(body().get('doctor_id'), exclude=case.doctor_id)
    case.doctor_id, case.status, case.status_reason = doctor.id, 'pending', None
    case.accepted_at = case.doctor_read_at = None
    case.draft, case.ai_draft, case.ai_model, case.ai_generated_at = None, None, None, None
    reset_deadline(case)
    record(case, 'reassigned', f'已改为由{doctor.name}接诊', g.user)
    notify(doctor.id, case, 'new_case', f'新病例：{case.title}',
           f'{case.profile_snapshot["name"]}，紧急程度：{URGENCY_LABELS[case.urgency]}')
    db.session.commit()
    db.session.refresh(case)
    return detail(case)


@bp.post('/cases/<int:case_id>/cancel')
@auth('patient')
def cancel(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'cancel')
    reason = reason_from(body(), required=False, label='撤回原因')
    was_accepted = case.status in ('processing', 'awaiting_info')
    case.status, case.status_reason, case.closed_at = 'cancelled', reason, now()
    record(case, 'cancelled', '患者撤回了病例', g.user, reason)
    if was_accepted:
        notify(case.doctor_id, case, 'cancelled', f'患者撤回了病例：{case.title}', reason or '')
    db.session.commit()
    return detail(case)


@bp.post('/cases/<int:case_id>/review')
@auth('patient')
def review(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'review')
    data = body()
    rating, text = data.get('rating'), data.get('review', '')
    if isinstance(rating, bool) or rating not in (1, 2, 3, 4, 5):
        return error('请选择 1 至 5 星评价')
    if not isinstance(text, str) or len(text) > 500:
        return error('评价内容最多 500 字')
    case.rating, case.review, case.reviewed_at = rating, text.strip(), now()
    notify(case.doctor_id, case, 'reviewed', f'患者评价了病例：{case.title}', f'{rating} 星 {text.strip()[:80]}')
    db.session.commit()
    return detail(case)


@bp.get('/cases/<int:case_id>/access-log')
@auth('patient')
def case_access_log(case_id):
    return jsonify(access_log(load_case(case_id)))


# ------------------------------------------------------------------ messages

@bp.get('/cases/<int:case_id>/messages')
@auth()
def list_messages(case_id):
    case = load_case(case_id)
    rows = db.session.execute(db.select(Message).where(Message.case_id == case.id).order_by(Message.id)).scalars().all()
    mark_read(case)
    db.session.commit()
    return jsonify([message_data(m, g.user) for m in rows])


@bp.post('/cases/<int:case_id>/messages')
@auth()
def send_message(case_id):
    case = load_case(case_id, lock=True)
    require(case, g.user, 'message')
    throttle(f'message:{g.user.id}', 40, 600, '发送过于频繁，请稍后再试')
    text = request.form.get('body', '').strip()
    validated = validate_uploads(request.files.getlist('attachments'), existing=len(case.attachments))
    if len(text) > 2000 or (not text and not validated):
        return error('请输入消息内容（最多 2000 字）或添加附件')
    written = []
    try:
        message = Message(case_id=case.id, sender_id=g.user.id, kind='message', body=text or f'发送了 {len(validated)} 个附件')
        db.session.add(message)
        db.session.flush()
        store(validated, case.id, g.user.id, message.id, written)
        recipient = case.doctor_id if g.user.role == 'patient' else case.patient_id
        who = '患者' if g.user.role == 'patient' else g.user.name
        notify(recipient, case, 'message', f'{who}发来消息：{case.title}', message.body[:100])
        mark_read(case)
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return jsonify(message_data(message, g.user)), 201


# ------------------------------------------------------------------- files

@bp.get('/cases/<int:case_id>/report/pdf')
@auth()
def download_report(case_id):
    case = load_case(case_id)
    if case.status != 'completed' or not case.report:
        return error('报告尚未发布', 409)
    audit('report_downloaded', case.id)
    db.session.commit()
    return send_file(report_pdf(case), mimetype='application/pdf', as_attachment=True,
                     download_name=f'MP-{case.id:06d}.pdf')


@bp.get('/attachments/<int:attachment_id>')
@auth()
def get_attachment(attachment_id):
    attachment = db.session.get(Attachment, attachment_id)
    if not attachment:
        return error('附件不存在', 404)
    case = load_case(attachment.case_id)
    if g.user.id != case.patient_id:
        audit('attachment_downloaded', case.id, attachment=attachment.id)
        db.session.commit()
    return send_file(Path(current_app.config['UPLOAD_DIR']) / attachment.storage_name, mimetype=attachment.mime,
                     as_attachment=True, download_name=attachment.name)


# ----------------------------------------------------------- notifications

@bp.get('/notifications')
@auth()
def notifications():
    rows = db.session.execute(db.select(Notification).where(Notification.user_id == g.user.id)
                              .order_by(Notification.created_at.desc()).limit(50)).scalars()
    return jsonify([{'id': n.id, 'kind': n.kind, 'title': n.title, 'body': n.body, 'case_id': n.case_id,
                     'read': n.read_at is not None, 'created_at': n.created_at.isoformat()} for n in rows])


@bp.post('/notifications/read')
@auth()
def read_notifications():
    ids = body().get('ids')
    query = db.update(Notification).where(Notification.user_id == g.user.id, Notification.read_at.is_(None))
    if isinstance(ids, list):
        query = query.where(Notification.id.in_([i for i in ids if isinstance(i, int)]))
    db.session.execute(query.values(read_at=now()))
    db.session.commit()
    return jsonify({'ok': True})


@bp.get('/summary')
@auth()
def summary():
    unread = db.session.execute(db.select(db.func.count()).select_from(Notification).where(
        Notification.user_id == g.user.id, Notification.read_at.is_(None))).scalar()
    return jsonify({'unread_notifications': unread})
