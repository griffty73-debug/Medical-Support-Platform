"""Case state machine: which action each role may take in each status, and the
side effects every transition shares (timeline events, notifications, deadlines).

Endpoints never compare status strings themselves; they call ``require`` and the
client renders exactly the actions returned by ``allowed_actions``.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from models import CaseEvent, Notification, db, now
from security import ApiError

TZ = ZoneInfo('Asia/Shanghai')

STATUS_LABELS = {
    'pending': '待接诊', 'processing': '评估中', 'awaiting_info': '待补充资料',
    'completed': '已完成', 'declined': '已退回', 'cancelled': '已撤回',
}
OPEN_STATUSES = frozenset({'pending', 'processing', 'awaiting_info'})
URGENCY_LABELS = {'emergency': '紧急', 'urgent': '尽快', 'routine': '常规'}
URGENCY_RANK = {'emergency': 0, 'urgent': 1, 'routine': 2}
RESPONSE_HOURS = {'emergency': 2, 'urgent': 12, 'routine': 48}
REPORT_TEXT_FIELDS = ('summary', 'basis', 'treatment', 'advice')
REPORT_LABELS = {'summary': '初步评估', 'basis': '判断依据', 'treatment': '处理建议', 'advice': '注意事项'}
VISIT_LABELS = {
    'none': '暂不需要线下就诊', 'routine': '建议择期到门诊就诊',
    'soon': '建议 24 小时内到医院就诊', 'emergency': '建议立即前往急诊',
}
FOLLOWUP_DAYS = (0, 3, 7, 14, 30)
MESSAGE_WINDOW_DAYS = 7
FOLLOWUP_WINDOW_DAYS = 14

ACTIONS = {
    'accept': ('doctor', {'pending'}),
    'decline': ('doctor', OPEN_STATUSES),
    'transfer': ('doctor', OPEN_STATUSES),
    'set_urgency': ('doctor', OPEN_STATUSES),
    'request_info': ('doctor', {'processing'}),
    'resume': ('doctor', {'awaiting_info'}),
    'edit_draft': ('doctor', {'processing', 'awaiting_info'}),
    'ai_draft': ('doctor', {'processing', 'awaiting_info'}),
    'publish': ('doctor', {'processing'}),
    'amend': ('doctor', {'completed'}),
    'supplement': ('patient', {'awaiting_info'}),
    'reassign': ('patient', {'pending', 'declined'}),
    'cancel': ('patient', {'pending', 'processing', 'awaiting_info', 'declined'}),
    'review': ('patient', {'completed'}),
    'followup': ('patient', {'completed'}),
}

BLOCKED = {
    'accept': '该病例已被接诊或已关闭',
    'publish': '仅评估中的病例可以发布报告；如在等待补充资料，请先结束等待',
    'ai_draft': '仅已接诊且患者授权 AI 辅助的病例可以生成 AI 草稿',
    'edit_draft': '当前状态不能编辑报告草稿',
    'amend': '仅已发布的报告可以更正',
    'supplement': '医生目前没有请求补充资料',
    'reassign': '仅待接诊或已退回的病例可以更换医生',
    'cancel': '该病例已完成或已关闭，无法撤回',
    'review': '该病例已评价或尚未完成',
    'followup': '该病例已有进行中的复诊',
    'message': '当前不在沟通期内，如需继续咨询请发起复诊',
}


def local_date(value=None):
    return (value or now()).astimezone(TZ).date()


def message_deadline(case):
    if case.status in OPEN_STATUSES:
        return None
    if case.status != 'completed' or not case.published_at:
        return now()
    ends = [case.published_at + timedelta(days=MESSAGE_WINDOW_DAYS)]
    if case.amended_at:
        ends.append(case.amended_at + timedelta(days=MESSAGE_WINDOW_DAYS))
    if case.followup_due:
        end_of_due = datetime.combine(case.followup_due, time.max, TZ)
        ends.append(end_of_due + timedelta(days=MESSAGE_WINDOW_DAYS))
    return max(ends)


def can_message(case, user):
    if case.status in OPEN_STATUSES:
        return user.role == 'patient' or case.status != 'pending'
    return case.status == 'completed' and now() <= message_deadline(case)


def has_open_followup(case):
    return any(child.status in OPEN_STATUSES for child in case.children)


def allowed_actions(case, user):
    if user.id not in (case.patient_id, case.doctor_id):
        return []
    result = []
    for name, (role, statuses) in ACTIONS.items():
        if role != user.role or case.status not in statuses:
            continue
        if name == 'ai_draft' and not case.consent_ai:
            continue
        if name == 'review' and case.rating:
            continue
        if name == 'followup' and has_open_followup(case):
            continue
        result.append(name)
    if can_message(case, user):
        result.append('message')
    return result


def require(case, user, action):
    if action not in allowed_actions(case, user):
        raise ApiError(BLOCKED.get(action, '病例状态已变化，请刷新后重试'), 409)


def higher_urgency(*levels):
    return min((level for level in levels if level in URGENCY_RANK), key=URGENCY_RANK.get, default='routine')


def reset_deadline(case):
    case.due_at = now() + timedelta(hours=RESPONSE_HOURS[case.urgency])


def is_overdue(case):
    return case.status == 'pending' and case.due_at is not None and now() > case.due_at


def record(case, kind, message, actor=None, detail=None):
    db.session.add(CaseEvent(case_id=case.id, kind=kind, message=message[:200],
                             actor_id=actor.id if actor else None, detail=detail))
    case.updated_at = now()


def notify(user_id, case, kind, title, body=''):
    """Queue an in-app notification. Repeated chat messages collapse into one unread item per case."""
    body = (body or '')[:300]
    if kind == 'message':
        existing = db.session.execute(db.select(Notification).where(
            Notification.user_id == user_id, Notification.case_id == case.id,
            Notification.kind == 'message', Notification.read_at.is_(None))).scalar_one_or_none()
        if existing:
            existing.title, existing.body, existing.created_at = title, body, now()
            return
    db.session.add(Notification(user_id=user_id, case_id=case.id, kind=kind, title=title[:100], body=body))
