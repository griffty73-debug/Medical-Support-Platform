"""Test fixtures. Tests use an in-memory SQLite database by default; set
TEST_DATABASE_URL to run the same suite against PostgreSQL."""
from io import BytesIO
import os
from pathlib import Path
import sys

os.environ['DATABASE_URL'] = os.getenv('TEST_DATABASE_URL', 'sqlite://')
os.environ['SECRET_KEY'] = 'test-secret-key-only-for-tests'
os.environ.pop('SILICONFLOW_API_KEY', None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image
from werkzeug.security import generate_password_hash

from app import app
from models import User, db
from security import limiter

DOCTOR_PASSWORD = 'Doctor123'
PATIENT_PASSWORD = 'Patient123'


def national_id(body='11010119960101123'):
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    return body + '10X98765432'[sum(int(d) * w for d, w in zip(body, weights)) % 11]


@pytest.fixture()
def client(tmp_path):
    app.config.update(TESTING=True, UPLOAD_DIR=str(tmp_path))
    limiter.reset()
    with app.app_context():
        db.drop_all()
        db.create_all()
        for index, (name, department, accepting) in enumerate(
                [('李医生', '全科医学科', True), ('王医生', '呼吸内科', True), ('赵医生', '皮肤科', False)], start=1):
            db.session.add(User(name=name, phone=f'1390000000{index}', role='doctor', department=department,
                                title='主治医师', accepting=accepting,
                                password_hash=generate_password_hash(DOCTOR_PASSWORD)))
        db.session.commit()
    yield app.test_client()
    with app.app_context():
        db.session.remove()
        db.drop_all()


def bearer(token):
    return {'Authorization': 'Bearer ' + token}


def register(client, phone='13800000001', name='测试患者'):
    response = client.post('/api/auth/register', json={'name': name, 'phone': phone, 'password': PATIENT_PASSWORD})
    assert response.status_code == 201, response.json
    return bearer(response.json['token'])


def login_doctor(client, index=1):
    response = client.post('/api/auth/login', json={'phone': f'1390000000{index}', 'password': DOCTOR_PASSWORD,
                                                    'role': 'doctor'})
    assert response.status_code == 200, response.json
    return bearer(response.json['token'])


def complete_profile(client, headers, **overrides):
    data = {'name': '测试患者', 'national_id': national_id(), 'allergies': '青霉素', 'history': '无',
            'medications': '无', **overrides}
    response = client.put('/api/profile', headers=headers, json=data)
    assert response.status_code == 200, response.json
    return response.json


def patient(client, phone='13800000001'):
    headers = register(client, phone)
    complete_profile(client, headers)
    return headers


def submit(client, headers, **fields):
    data = {'title': '咳嗽三天', 'description': '三天前开始咳嗽，伴有咽部不适，无发热。', 'duration': '3 天',
            'doctor_id': '1', 'consent_share': 'true', 'consent_ai': 'true', **fields}
    return client.post('/api/cases', headers=headers, data=data)


def png(name='检查.png'):
    stream = BytesIO()
    Image.new('RGB', (12, 12), 'white').save(stream, 'PNG')
    stream.seek(0)
    return stream, name


def full_report(**overrides):
    return {'summary': '上呼吸道感染可能', 'basis': '咳嗽三天，无发热', 'treatment': '多饮水，注意休息',
            'advice': '如出现气促请及时就医', 'visit': 'none', 'followup_days': 7, **overrides}


def accepted_case(client, patient_headers=None, doctor_index=1, **fields):
    patient_headers = patient_headers or patient(client)
    case = submit(client, patient_headers, doctor_id=str(doctor_index), **fields).json
    doctor = login_doctor(client, doctor_index)
    assert client.post(f'/api/cases/{case["id"]}/accept', headers=doctor).status_code == 200
    return case['id'], patient_headers, doctor


def publish(client, case_id, doctor, **report):
    detail = client.get(f'/api/cases/{case_id}', headers=doctor).json
    response = client.post(f'/api/cases/{case_id}/publish', headers=doctor,
                           json={'version': detail['report_version'], 'report': full_report(**report), 'confirmed': True})
    assert response.status_code == 200, response.json
    return response.json
