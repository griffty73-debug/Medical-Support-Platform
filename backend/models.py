from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa

db = SQLAlchemy()


def now():
    return datetime.now(timezone.utc)


class UTCDateTime(sa.TypeDecorator):
    """Timezone-aware timestamps on every backend (SQLite drops the offset when storing)."""
    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    # Age and gender are derived from the national ID once it is on file; the
    # stored values are kept for records created before the ID was required.
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    national_id_encrypted = db.Column(db.Text)
    allergies = db.Column(db.Text, default='')
    history = db.Column(db.Text, default='')
    medications = db.Column(db.Text, default='')
    department = db.Column(db.String(60))
    title = db.Column(db.String(60))
    specialty = db.Column(db.Text)
    avatar = db.Column(db.String(200))
    created_at = db.Column(UTCDateTime, default=now)
    accepting = db.Column(db.Boolean, nullable=False, default=True, server_default=sa.true())
    token_version = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    failed_logins = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    locked_until = db.Column(UTCDateTime)
    last_login_at = db.Column(UTCDateTime)
    password_changed_at = db.Column(UTCDateTime)


class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False, default='initial', server_default='initial')
    parent_id = db.Column(db.Integer, db.ForeignKey('case.id'), index=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    duration = db.Column(db.String(100), default='')
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    status_reason = db.Column(db.String(500))
    urgency = db.Column(db.String(20), nullable=False, default='routine', server_default='routine')
    triage = db.Column(db.JSON)
    answers = db.Column(db.JSON)
    profile_snapshot = db.Column(db.JSON, nullable=False)
    consent_ai = db.Column(db.Boolean, nullable=False)
    consent_at = db.Column(UTCDateTime)
    consent_version = db.Column(db.String(20))
    # draft is the doctor's working copy; report is what the patient sees.
    draft = db.Column(db.JSON)
    report = db.Column(db.JSON)
    report_version = db.Column(db.Integer, default=0, nullable=False)
    published_version = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    ai_model = db.Column(db.String(100))
    ai_generated_at = db.Column(UTCDateTime)
    ai_draft = db.Column(db.JSON)
    ai_edit_ratio = db.Column(db.Float)
    followup_due = db.Column(db.Date)
    rating = db.Column(db.SmallInteger)
    review = db.Column(db.Text)
    reviewed_at = db.Column(UTCDateTime)
    patient_read_at = db.Column(UTCDateTime)
    doctor_read_at = db.Column(UTCDateTime)
    created_at = db.Column(UTCDateTime, default=now)
    updated_at = db.Column(UTCDateTime, default=now, onupdate=now)
    due_at = db.Column(UTCDateTime)
    accepted_at = db.Column(UTCDateTime)
    published_at = db.Column(UTCDateTime)
    amended_at = db.Column(UTCDateTime)
    closed_at = db.Column(UTCDateTime)
    patient = db.relationship(User, foreign_keys=[patient_id])
    doctor = db.relationship(User, foreign_keys=[doctor_id])
    parent = db.relationship('Case', remote_side=[id], foreign_keys=[parent_id], backref='children')
    attachments = db.relationship('Attachment', cascade='all, delete-orphan', lazy='selectin', order_by='Attachment.id')
    events = db.relationship('CaseEvent', cascade='all, delete-orphan', lazy='selectin', order_by='CaseEvent.id')


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(200), nullable=False)
    storage_name = db.Column(db.String(100), nullable=False)
    mime = db.Column(db.String(80), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(UTCDateTime, default=now)


class CaseEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    kind = db.Column(db.String(30), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    detail = db.Column(db.Text)
    created_at = db.Column(UTCDateTime, default=now)


class ReportHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(30), nullable=False)
    content = db.Column(db.JSON, nullable=False)
    reason = db.Column(db.String(500))
    created_at = db.Column(UTCDateTime, default=now)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default='message')
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(UTCDateTime, default=now)
    sender = db.relationship(User)
    attachments = db.relationship(Attachment, lazy='selectin', order_by=Attachment.id, viewonly=True)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'))
    kind = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    body = db.Column(db.String(300), nullable=False, default='')
    created_at = db.Column(UTCDateTime, default=now, index=True)
    read_at = db.Column(UTCDateTime)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    action = db.Column(db.String(40), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), index=True)
    ip = db.Column(db.String(64))
    detail = db.Column(db.JSON)
    created_at = db.Column(UTCDateTime, default=now, index=True)


class TriageSession(db.Model):
    """A pre-consultation result, bound to the patient and the exact text it assessed."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    fingerprint = db.Column(db.String(64), nullable=False)
    result = db.Column(db.JSON, nullable=False)
    created_at = db.Column(UTCDateTime, default=now)
