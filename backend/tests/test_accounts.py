from conftest import (DOCTOR_PASSWORD, PATIENT_PASSWORD, bearer, complete_profile, login_doctor, national_id,
                      register)
from models import AuditLog, User, db
from app import app


def test_registration_rules(client):
    weak = client.post('/api/auth/register', json={'name': '患者', 'phone': '13800000001', 'password': 'abcdefgh'})
    assert weak.status_code == 400 and '字母和数字' in weak.json['error']
    register(client)
    again = client.post('/api/auth/register', json={'name': '患者', 'phone': '13800000001', 'password': PATIENT_PASSWORD})
    assert again.status_code == 409


def test_login_lockout_and_role_separation(client):
    register(client)
    for attempt in range(4):
        response = client.post('/api/auth/login', json={'phone': '13800000001', 'password': 'Wrong1234', 'role': 'patient'})
        assert response.status_code == 401
    assert '再错 1 次' in response.json['error']
    locked = client.post('/api/auth/login', json={'phone': '13800000001', 'password': 'Wrong1234', 'role': 'patient'})
    assert '已锁定' in locked.json['error']
    correct = client.post('/api/auth/login', json={'phone': '13800000001', 'password': PATIENT_PASSWORD, 'role': 'patient'})
    assert correct.status_code == 423
    wrong_portal = client.post('/api/auth/login', json={'phone': '13900000001', 'password': DOCTOR_PASSWORD, 'role': 'patient'})
    assert wrong_portal.status_code == 403
    unknown = client.post('/api/auth/login', json={'phone': '13700000000', 'password': 'Whatever1', 'role': 'patient'})
    assert unknown.status_code == 401
    with app.app_context():
        actions = [a for (a,) in db.session.execute(db.select(AuditLog.action))]
        assert actions.count('login_failed') == 5 and 'login_locked' in actions


def test_password_change_revokes_old_sessions(client):
    old = register(client)
    assert client.post('/api/auth/password', headers=old,
                       json={'current_password': 'Nope12345', 'new_password': 'Newpass123'}).status_code == 400
    changed = client.post('/api/auth/password', headers=old,
                          json={'current_password': PATIENT_PASSWORD, 'new_password': 'Newpass123'})
    assert changed.status_code == 200
    assert client.get('/api/auth/me', headers=old).status_code == 401
    assert client.get('/api/auth/me', headers=bearer(changed.json['token'])).status_code == 200
    revoked = client.post('/api/auth/logout-others', headers=bearer(changed.json['token']))
    assert client.get('/api/auth/me', headers=bearer(changed.json['token'])).status_code == 401
    assert client.get('/api/auth/me', headers=bearer(revoked.json['token'])).status_code == 200


def test_profile_identity_is_validated_derived_and_masked(client):
    headers = register(client)
    bad = client.put('/api/profile', headers=headers, json={'name': '测试', 'national_id': national_id()[:-1] + ('1' if national_id()[-1] != '1' else '2'),
                                                           'allergies': '无', 'medications': '无'})
    assert bad.status_code == 400 and '校验位' in bad.json['error']
    missing = client.put('/api/profile', headers=headers, json={'name': '测试', 'national_id': national_id(),
                                                               'allergies': '', 'medications': '无'})
    assert missing.status_code == 400
    profile = complete_profile(client, headers, national_id=national_id('11010119900307002'))
    assert profile['gender'] == '女' and profile['birth_date'] == '1990-03-07' and profile['complete']
    assert profile['national_id_masked'].startswith('110') and '1990' not in profile['national_id_masked']
    assert 'national_id' not in client.get('/api/profile', headers=headers).json
    kept = client.put('/api/profile', headers=headers, json={'name': '测试改名', 'allergies': '无', 'history': '',
                                                            'medications': '无'})
    assert kept.status_code == 200 and kept.json['has_national_id'] and kept.json['name'] == '测试改名'
    reveal = client.post('/api/profile/reveal-id', headers=headers)
    assert reveal.json['national_id'] == national_id('11010119900307002')
    with app.app_context():
        assert db.session.execute(db.select(AuditLog).where(AuditLog.action == 'national_id_revealed')).scalar()
        stored = db.session.execute(db.select(User).where(User.phone == '13800000001')).scalar_one()
        assert '1990' not in stored.national_id_encrypted


def test_doctor_availability(client):
    doctor = login_doctor(client)
    paused = client.put('/api/account/doctor', headers=doctor, json={'accepting': False, 'specialty': '慢病管理'})
    assert paused.status_code == 200 and paused.json['accepting'] is False
    directory = client.get('/api/doctors', headers=doctor).json
    assert [d['accepting'] for d in directory] == [True, False, False]
    assert client.put('/api/account/doctor', headers=register(client), json={}).status_code == 403
