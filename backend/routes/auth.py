from datetime import timedelta
import math

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, db, now
from security import (LOCK_MINUTES, LOCK_THRESHOLD, PHONE, ApiError, age_on, audit, auth, client_ip, decrypt, encrypt,
                      error, issue_token, parse_national_id, password_problem, throttle)
from serializers import account_data, doctor_directory, profile_data

bp = Blueprint('auth', __name__)
# Compared against when the phone number is unknown, so both paths cost the same time.
_DUMMY_HASH = generate_password_hash('timing-equaliser-not-a-password')


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@bp.post('/auth/register')
def register():
    throttle(f'register:{client_ip()}', 10, 3600, '注册过于频繁，请稍后再试')
    data = _json()
    name, phone, password = data.get('name', ''), data.get('phone', ''), data.get('password', '')
    if not all(isinstance(v, str) for v in (name, phone, password)):
        return error('注册信息无效')
    if not name.strip() or len(name.strip()) > 50:
        return error('请输入姓名（不超过 50 字）')
    if not PHONE.fullmatch(phone):
        return error('请输入有效的 11 位手机号码')
    problem = password_problem(password)
    if problem:
        return error(problem)
    user = User(name=name.strip(), phone=phone, password_hash=generate_password_hash(password), role='patient',
                password_changed_at=now(), last_login_at=now())
    db.session.add(user)
    try:
        db.session.flush()
        audit('register', user=user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error('该手机号已注册，请直接登录', 409)
    return jsonify({'token': issue_token(user), 'user': account_data(user)}), 201


@bp.post('/auth/login')
def login():
    throttle(f'login:{client_ip()}', 30, 600, '登录尝试过于频繁，请 10 分钟后再试')
    data = _json()
    phone, password = data.get('phone'), data.get('password')
    if not isinstance(phone, str) or not isinstance(password, str) or len(password) > 128:
        return error('请输入手机号和密码')
    user = db.session.execute(db.select(User).where(User.phone == phone).with_for_update()).scalar_one_or_none()
    if user and user.locked_until and user.locked_until > now():
        minutes = math.ceil((user.locked_until - now()).total_seconds() / 60)
        return error(f'密码错误次数过多，账号已临时锁定，请 {minutes} 分钟后再试', 423)
    if not user:
        check_password_hash(_DUMMY_HASH, password)
        return error('手机号或密码错误', 401)
    if not check_password_hash(user.password_hash, password):
        user.failed_logins += 1
        message = '手机号或密码错误'
        if user.failed_logins >= LOCK_THRESHOLD:
            user.failed_logins = 0
            user.locked_until = now() + timedelta(minutes=LOCK_MINUTES)
            message = f'密码错误次数过多，账号已锁定 {LOCK_MINUTES} 分钟'
            audit('login_locked', user=user)
        elif LOCK_THRESHOLD - user.failed_logins <= 2:
            message += f'，再错 {LOCK_THRESHOLD - user.failed_logins} 次将锁定 {LOCK_MINUTES} 分钟'
        audit('login_failed', user=user)
        db.session.commit()
        return error(message, 401)
    if data.get('role') != user.role:
        db.session.rollback()
        return error('请在对应的用户端或医生端登录', 403)
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now()
    audit('login', user=user)
    db.session.commit()
    return jsonify({'token': issue_token(user), 'user': account_data(user)})


@bp.get('/auth/me')
@auth()
def me():
    return jsonify(account_data(g.user))


@bp.post('/auth/password')
@auth()
def change_password():
    throttle(f'password:{g.user.id}', 10, 3600)
    data = _json()
    current, new = data.get('current_password'), data.get('new_password')
    if not isinstance(current, str) or not check_password_hash(g.user.password_hash, current):
        audit('password_change_failed')
        db.session.commit()
        return error('当前密码不正确', 400)
    problem = password_problem(new)
    if problem:
        return error(problem)
    if current == new:
        return error('新密码不能与当前密码相同')
    g.user.password_hash = generate_password_hash(new)
    g.user.password_changed_at = now()
    g.user.token_version += 1
    audit('password_changed')
    db.session.commit()
    return jsonify({'token': issue_token(g.user), 'user': account_data(g.user)})


@bp.post('/auth/logout-others')
@auth()
def logout_others():
    g.user.token_version += 1
    audit('sessions_revoked')
    db.session.commit()
    return jsonify({'token': issue_token(g.user)})


# ------------------------------------------------------------------- profile

@bp.get('/profile')
@auth('patient')
def get_profile():
    return jsonify(profile_data(g.user))


@bp.put('/profile')
@auth('patient')
def update_profile():
    data = _json()
    fields = ('name', 'national_id', 'allergies', 'history', 'medications')
    if not all(isinstance(data.get(f, ''), str) for f in fields):
        return error('档案字段格式无效')
    name = data.get('name', '').strip()
    if not name or len(name) > 50:
        return error('请输入有效姓名')
    national_id = data.get('national_id', '').strip().upper()
    if not national_id and not g.user.national_id_encrypted:
        return error('请输入身份证号码')
    if national_id:
        try:
            birth, gender = parse_national_id(national_id)
        except ValueError as exc:
            return error(str(exc))
    for field in ('allergies', 'medications'):
        if not data.get(field, '').strip():
            return error('请填写过敏史和当前用药；如没有，请填写“无”')
    if any(len(data.get(f, '')) > 3000 for f in ('allergies', 'history', 'medications')):
        return error('健康信息单项最多 3000 字')
    changed = [f for f in ('name', 'allergies', 'history', 'medications')
               if (getattr(g.user, f) or '') != data.get(f, '').strip()]
    g.user.name = name
    for field in ('allergies', 'history', 'medications'):
        setattr(g.user, field, data.get(field, '').strip())
    if national_id and national_id != decrypt(g.user.national_id_encrypted):
        g.user.national_id_encrypted = encrypt(national_id)
        g.user.age, g.user.gender = age_on(birth), gender
        changed.append('national_id')
    if changed:
        audit('profile_updated', fields=changed)
    db.session.commit()
    return jsonify(profile_data(g.user))


@bp.post('/profile/reveal-id')
@auth('patient')
def reveal_own_id():
    audit('national_id_revealed', scope='own_profile')
    db.session.commit()
    return jsonify({'national_id': decrypt(g.user.national_id_encrypted)})


@bp.put('/account/doctor')
@auth('doctor')
def update_doctor():
    data = _json()
    specialty, accepting = data.get('specialty', g.user.specialty or ''), data.get('accepting', g.user.accepting)
    if not isinstance(specialty, str) or len(specialty) > 500 or not isinstance(accepting, bool):
        return error('擅长领域最多 500 字')
    if accepting != g.user.accepting:
        audit('accepting_changed', accepting=accepting)
    g.user.specialty, g.user.accepting = specialty.strip(), accepting
    db.session.commit()
    return jsonify(account_data(g.user))


@bp.get('/doctors')
@auth()
def doctors():
    users = db.session.execute(db.select(User).where(User.role == 'doctor')
                               .order_by(User.accepting.desc(), User.id)).scalars().all()
    return jsonify(doctor_directory(users))


def register_errors(app):
    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        db.session.rollback()
        return error(exc.message, exc.status)

