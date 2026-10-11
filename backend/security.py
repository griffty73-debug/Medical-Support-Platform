"""Authentication, encryption, identity validation, rate limiting and audit logging."""
import base64
from collections import defaultdict, deque
from datetime import date, timedelta
from functools import wraps
import hashlib
import re
import threading
import time

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, g, has_request_context, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from models import AuditLog, User, db, now

PHONE = re.compile(r'^1[3-9]\d{9}$')
NATIONAL_ID = re.compile(r'^\d{17}[\dX]$')
TOKEN_MAX_AGE = 12 * 3600
LOCK_THRESHOLD = 5
LOCK_MINUTES = 15


def error(message, status=400, **extra):
    return jsonify({'error': message, **extra}), status


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# ---------------------------------------------------------------- encryption

def cipher():
    key = hashlib.sha256(current_app.config['SECRET_KEY'].encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value):
    return cipher().encrypt(value.encode()).decode() if value else ''


def decrypt(value):
    if not value:
        return ''
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken:
        current_app.logger.error('Encrypted identity could not be decrypted; SECRET_KEY may have changed')
        return ''


# ------------------------------------------------------------- national ID

_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_CHECK = '10X98765432'


def parse_national_id(value):
    """Validate an 18-digit resident ID (checksum and birth date); return (birth_date, gender)."""
    value = (value or '').strip().upper()
    if not NATIONAL_ID.fullmatch(value):
        raise ValueError('请输入 18 位身份证号码')
    if _CHECK[sum(int(d) * w for d, w in zip(value[:17], _WEIGHTS)) % 11] != value[17]:
        raise ValueError('身份证号码校验位不正确，请检查后重新输入')
    try:
        birth = date(int(value[6:10]), int(value[10:12]), int(value[12:14]))
    except ValueError as exc:
        raise ValueError('身份证号码中的出生日期无效') from exc
    if birth > date.today() or birth.year < 1900:
        raise ValueError('身份证号码中的出生日期无效')
    return birth, '男' if int(value[16]) % 2 else '女'


def age_on(birth, day=None):
    day = day or date.today()
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def mask_id(value):
    return f'{value[:3]}{"*" * 11}{value[-4:]}' if value else ''


def mask_phone(value):
    return f'{value[:3]}****{value[-4:]}' if value and len(value) == 11 else value


# ------------------------------------------------------------------ passwords

def password_problem(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return '密码长度应为 8 至 128 位'
    if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
        return '密码需同时包含字母和数字'
    return None


# --------------------------------------------------------------------- tokens

def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def issue_token(user):
    return _serializer().dumps({'uid': user.id, 'tv': user.token_version}, salt='access-token')


def auth(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            header = request.headers.get('Authorization', '')
            if not header.startswith('Bearer '):
                return error('请先登录', 401)
            try:
                payload = _serializer().loads(header[7:], salt='access-token', max_age=TOKEN_MAX_AGE)
                user = db.session.get(User, payload['uid'])
            except (BadSignature, SignatureExpired, KeyError, TypeError):
                return error('登录已过期，请重新登录', 401)
            if not user or payload.get('tv', 0) != user.token_version:
                return error('登录已失效，请重新登录', 401)
            if role and user.role != role:
                return error('无权执行此操作', 403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapped
    return decorator


# --------------------------------------------------------------- rate limits

class RateLimiter:
    """In-process sliding-window limiter. Account lockout in the database is the
    durable protection; this layer slows bursts from a single client."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key, limit, window):
        if current_app.config.get('RATELIMIT_DISABLED'):
            return True
        stamp = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= stamp - window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(stamp)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip():
    return request.remote_addr or 'unknown'


def throttle(key, limit, window, message='操作过于频繁，请稍后再试'):
    if not limiter.hit(key, limit, window):
        raise ApiError(message, 429)


# ---------------------------------------------------------------------- audit

def audit(action, case_id=None, user=None, dedupe_minutes=0, **detail):
    """Record access to personal health information and security-relevant actions."""
    user_id = user.id if user else getattr(g, 'user', None) and g.user.id
    if dedupe_minutes and user_id:
        recent = db.session.execute(db.select(AuditLog.id).where(
            AuditLog.user_id == user_id, AuditLog.action == action, AuditLog.case_id == case_id,
            AuditLog.created_at >= now() - timedelta(minutes=dedupe_minutes)).limit(1)).first()
        if recent:
            return
    db.session.add(AuditLog(user_id=user_id, action=action, case_id=case_id,
                            ip=client_ip() if has_request_context() else None, detail=detail or None))
