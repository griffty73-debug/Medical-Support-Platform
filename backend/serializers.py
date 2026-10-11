"""JSON shapes returned by the API. Identity numbers are always masked here;
full values are only available through audited reveal endpoints."""
from datetime import timedelta

from sqlalchemy import func

from models import AuditLog, Case, Message, User, db
from security import age_on, decrypt, mask_id, mask_phone, parse_national_id
from workflow import (OPEN_STATUSES, STATUS_LABELS, URGENCY_LABELS, allowed_actions, is_overdue,
                      local_date, message_deadline, FOLLOWUP_WINDOW_DAYS)


def timestamp(value):
    return value.isoformat() if value else None


def public_user(user):
    return {'id': user.id, 'name': user.name, 'role': user.role, 'department': user.department,
            'title': user.title, 'specialty': user.specialty or '', 'accepting': user.accepting}


def account_data(user):
    return {**public_user(user), 'phone': user.phone, 'last_login_at': timestamp(user.last_login_at),
            'password_changed_at': timestamp(user.password_changed_at)}


def identity(user):
    """Age and gender come from the national ID when available."""
    national_id = decrypt(user.national_id_encrypted)
    if national_id:
        try:
            birth, gender = parse_national_id(national_id)
            return national_id, age_on(birth), gender, birth.isoformat()
        except ValueError:
            pass
    return national_id, user.age, user.gender, None


def profile_complete(user):
    national_id, age, gender, _ = identity(user)
    return bool(national_id and age is not None and gender and user.name
                and (user.allergies or '').strip() and (user.medications or '').strip())


def profile_data(user):
    national_id, age, gender, birth = identity(user)
    return {**account_data(user), 'age': age, 'gender': gender, 'birth_date': birth,
            'has_national_id': bool(national_id), 'national_id_masked': mask_id(national_id),
            'allergies': user.allergies or '', 'history': user.history or '',
            'medications': user.medications or '', 'complete': profile_complete(user)}


def snapshot(user):
    national_id, age, gender, _ = identity(user)
    return {'name': user.name, 'age': age, 'gender': gender, 'phone': user.phone,
            'allergies': user.allergies or '', 'history': user.history or '',
            'medications': user.medications or '', 'national_id_encrypted': user.national_id_encrypted}


def doctor_directory(doctors):
    ids = [d.id for d in doctors]
    if not ids:
        return []
    ratings = dict((row[0], (row[1], row[2])) for row in db.session.execute(
        db.select(Case.doctor_id, func.avg(Case.rating), func.count(Case.rating))
        .where(Case.doctor_id.in_(ids), Case.rating.is_not(None)).group_by(Case.doctor_id)))
    waiting = dict(db.session.execute(
        db.select(Case.doctor_id, func.count()).where(Case.doctor_id.in_(ids), Case.status == 'pending')
        .group_by(Case.doctor_id)).all())
    result = []
    for doctor in doctors:
        average, count = ratings.get(doctor.id, (None, 0))
        result.append({**public_user(doctor), 'rating': round(float(average), 1) if average else None,
                       'rating_count': count, 'waiting': waiting.get(doctor.id, 0)})
    return result


def unread_count(case, user):
    read_at = case.patient_read_at if user.role == 'patient' else case.doctor_read_at
    query = db.select(func.count()).select_from(Message).where(Message.case_id == case.id, Message.sender_id != user.id)
    if read_at:
        query = query.where(Message.created_at > read_at)
    return db.session.execute(query).scalar()


def followup_state(case):
    """Whether a follow-up visit is due: 'upcoming' (within 2 days), 'due', or None."""
    if case.status != 'completed' or not case.followup_due:
        return None
    if any(child.created_at and child.created_at > (case.amended_at or case.published_at) for child in case.children):
        return 'returned'
    today = local_date()
    if today > case.followup_due + timedelta(days=FOLLOWUP_WINDOW_DAYS):
        return None
    if today >= case.followup_due:
        return 'due'
    if today >= case.followup_due - timedelta(days=2):
        return 'upcoming'
    return 'scheduled'


def case_summary(case, user):
    result = {
        'id': case.id, 'number': f'MP-{case.id:06d}', 'title': case.title, 'kind': case.kind,
        'status': case.status, 'status_label': STATUS_LABELS[case.status], 'urgency': case.urgency,
        'urgency_label': URGENCY_LABELS[case.urgency],
        'patient': {'id': case.patient_id, 'name': case.profile_snapshot['name'],
                    'age': case.profile_snapshot.get('age'), 'gender': case.profile_snapshot.get('gender')},
        'doctor': public_user(case.doctor), 'created_at': timestamp(case.created_at),
        'updated_at': timestamp(case.updated_at), 'published_at': timestamp(case.published_at),
        'due_at': timestamp(case.due_at), 'overdue': is_overdue(case),
        'followup_due': case.followup_due.isoformat() if case.followup_due else None,
        'followup_state': followup_state(case), 'attachment_count': len(case.attachments),
        'unread': unread_count(case, user), 'parent_id': case.parent_id,
        'rating': case.rating if user.role == 'doctor' or user.id == case.patient_id else None,
    }
    if user.role == 'doctor':
        result['flags'] = [f['label'] for f in (case.triage or {}).get('flags', [])]
    return result


def triage_view(case, user):
    triage = case.triage or {}
    ai = triage.get('ai') or {}
    data = {'level': triage.get('level', case.urgency), 'flags': triage.get('flags', []),
            'department': ai.get('department'), 'patient_advice': ai.get('patient_advice')}
    if user.role == 'doctor':
        data.update(ai_summary=ai.get('doctor_summary'), ai_red_flags=ai.get('red_flags', []),
                    ai_model=ai.get('model'), ai_level=ai.get('level'))
    return data


def event_data(event, users):
    actor = users.get(event.actor_id)
    return {'kind': event.kind, 'message': event.message, 'detail': event.detail,
            'actor': {'name': actor.name, 'role': actor.role} if actor else None,
            'created_at': timestamp(event.created_at)}


def attachment_data(attachment, users):
    uploader = users.get(attachment.uploaded_by)
    return {'id': attachment.id, 'name': attachment.name, 'mime': attachment.mime, 'size': attachment.size,
            'message_id': attachment.message_id, 'created_at': timestamp(attachment.created_at),
            'uploaded_by': uploader.role if uploader else 'patient'}


def case_detail(case, user):
    users = {u.id: u for u in db.session.execute(db.select(User).where(
        User.id.in_(({e.actor_id for e in case.events} | {a.uploaded_by for a in case.attachments}) - {None}))).scalars()}
    profile = {k: v for k, v in case.profile_snapshot.items() if k != 'national_id_encrypted'}
    profile['national_id_masked'] = mask_id(decrypt(case.profile_snapshot.get('national_id_encrypted', '')))
    if user.role == 'doctor':
        profile['phone'] = mask_phone(profile.get('phone'))  # contact happens through in-platform messages
    result = case_summary(case, user)
    result.update(
        description=case.description, duration=case.duration, profile=profile,
        status_reason=case.status_reason, triage=triage_view(case, user), answers=case.answers or [],
        consent_ai=case.consent_ai, accepted_at=timestamp(case.accepted_at), amended_at=timestamp(case.amended_at),
        closed_at=timestamp(case.closed_at), published_version=case.published_version,
        attachments=[attachment_data(a, users) for a in case.attachments],
        events=[event_data(e, users) for e in case.events],
        actions=allowed_actions(case, user),
        message_until=timestamp(message_deadline(case)) if case.status not in OPEN_STATUSES else None,
        parent={'id': case.parent.id, 'number': f'MP-{case.parent.id:06d}', 'title': case.parent.title,
                'report': case.parent.report if user.role == 'doctor' else None,
                'published_at': timestamp(case.parent.published_at)} if case.parent else None,
        children=[{'id': c.id, 'number': f'MP-{c.id:06d}', 'title': c.title, 'status': c.status,
                   'status_label': STATUS_LABELS[c.status]} for c in case.children],
        review=case.review if case.rating else None,
    )
    if case.status == 'completed' or case.published_version:
        result['report'] = case.report
    if user.role == 'doctor':
        result.update(draft=case.draft, report_version=case.report_version, ai_model=case.ai_model,
                      ai_generated_at=timestamp(case.ai_generated_at), ai_edit_ratio=case.ai_edit_ratio)
    return result


def message_data(message, viewer):
    return {'id': message.id, 'kind': message.kind, 'body': message.body, 'mine': message.sender_id == viewer.id,
            'sender': {'name': message.sender.name, 'role': message.sender.role},
            'attachments': [{'id': a.id, 'name': a.name, 'mime': a.mime, 'size': a.size} for a in message.attachments],
            'created_at': timestamp(message.created_at)}


ACCESS_LABELS = {'case_viewed': '查看了病例', 'attachment_downloaded': '下载了附件',
                 'national_id_revealed': '查看了完整身份证号', 'report_downloaded': '下载了报告',
                 'ai_draft': '使用 AI 生成报告草稿', 'ai_pre_consult': '使用 AI 预问诊'}


def access_log(case):
    rows = db.session.execute(db.select(AuditLog, User).join(User, AuditLog.user_id == User.id)
                              .where(AuditLog.case_id == case.id, AuditLog.action.in_(ACCESS_LABELS))
                              .order_by(AuditLog.id.desc()).limit(100)).all()
    return [{'action': log.action, 'label': ACCESS_LABELS[log.action], 'name': who.name,
             'role': who.role, 'created_at': timestamp(log.created_at)} for log, who in rows]

