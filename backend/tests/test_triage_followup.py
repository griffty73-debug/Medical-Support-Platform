from datetime import date, timedelta

import pytest

import routes.cases as case_routes
from app import app
from conftest import accepted_case, login_doctor, patient, png, publish, submit
from models import Case, Notification, db, now
import triage


@pytest.mark.parametrize('text, level, label', [
    ('胸痛三小时，伴出汗', 'emergency', '胸痛'),
    ('突然说话不清，右侧手脚无力', 'emergency', '疑似脑卒中表现'),
    ('最近总觉得不想活了', 'emergency', '心理危机'),
    ('发烧 39.5 度两天', 'urgent', '高热'),
    ('咳嗽三天，无胸痛，没有呼吸困难', 'routine', None),
    ('既往骨折术后，现在膝盖酸', 'routine', None),
    ('喉咙有点痒，鼻塞', 'routine', None),
])
def test_red_flag_rules(text, level, label):
    result = triage.assess('症状', text)
    assert result['level'] == level
    assert (result['flags'][0]['label'] if result['flags'] else None) == label


def test_crisis_flag_points_to_hotline():
    flags = triage.assess('情绪', '我想结束自己的生命')['flags']
    assert flags[0]['level'] == 'crisis' and '12356' in flags[0]['advice']


def test_pre_consult_binds_ai_result_to_the_assessed_text(client, monkeypatch):
    headers = patient(client)
    body = {'title': '咳嗽三天', 'description': '三天前开始咳嗽，伴有咽部不适，无发热。', 'duration': '3 天'}
    rules_only = client.post('/api/triage', headers=headers, json=body)
    assert rules_only.json['level'] == 'routine' and rules_only.json['ai'] is None

    unavailable = client.post('/api/triage', headers=headers, json={**body, 'use_ai': True})
    assert unavailable.status_code == 200 and '暂不可用' in unavailable.json['ai_error']

    fake = {'level': 'urgent', 'red_flags': ['咳嗽持续'], 'department': '呼吸内科', 'questions': ['是否有痰？'],
            'patient_advice': '多喝水', 'doctor_summary': '青年女性，咳嗽三天。', 'model': 'test-qwen'}
    monkeypatch.setattr(case_routes.ai, 'configured', lambda: True)
    monkeypatch.setattr(case_routes.ai, 'pre_consult', lambda *args: dict(fake))
    assisted = client.post('/api/triage', headers=headers, json={**body, 'use_ai': True}).json
    assert assisted['level'] == 'urgent' and assisted['ai']['questions'] == ['是否有痰？']
    assert 'doctor_summary' not in assisted['ai']

    answers = '[{"q": "是否有痰？", "a": "白色痰"}]'
    case = submit(client, headers, triage_id=str(assisted['id']), answers=answers).json
    assert case['urgency'] == 'urgent' and case['answers'] == [{'q': '是否有痰？', 'a': '白色痰'}]
    doctor_view = client.get(f'/api/cases/{case["id"]}', headers=login_doctor(client)).json
    assert doctor_view['triage']['ai_summary'] == '青年女性，咳嗽三天。'
    assert 'ai_summary' not in client.get(f'/api/cases/{case["id"]}', headers=headers).json['triage']

    edited = submit(client, headers, triage_id=str(assisted['id']), description='三天前开始咳嗽，今天加重了很多。').json
    assert edited['urgency'] == 'routine'
    declined_ai = submit(client, headers, triage_id=str(assisted['id']), consent_ai='false').json
    assert declined_ai['urgency'] == 'routine' and declined_ai['triage']['department'] is None
    stranger = patient(client, '13800000002')
    borrowed = submit(client, stranger, triage_id=str(assisted['id'])).json
    assert borrowed['urgency'] == 'routine'


def test_rules_raise_urgency_and_queue_metadata(client):
    headers = patient(client)
    case = submit(client, headers, title='胸口疼', description='今天早上开始胸痛，持续不缓解，出冷汗。').json
    assert case['urgency'] == 'emergency'
    doctor = login_doctor(client)
    listed = client.get('/api/cases', headers=doctor).json[0]
    assert listed['flags'] == ['胸痛'] and listed['overdue'] is False
    with app.app_context():
        db.session.get(Case, case['id']).due_at = now() - timedelta(minutes=1)
        db.session.commit()
        assert db.session.execute(db.select(Notification.title)).scalar().startswith('【紧急】')
    assert client.get('/api/cases', headers=doctor).json[0]['overdue'] is True
    lowered = client.post(f'/api/cases/{case["id"]}/urgency', headers=doctor, json={'urgency': 'urgent'})
    assert lowered.json['urgency'] == 'urgent' and lowered.json['overdue'] is False


def test_messaging_rules_and_unread_counts(client):
    headers = patient(client)
    case_id = submit(client, headers).json['id']
    doctor = login_doctor(client)
    assert client.post(f'/api/cases/{case_id}/messages', headers=headers, data={'body': '补充：夜间咳得更厉害'}).status_code == 201
    assert client.post(f'/api/cases/{case_id}/messages', headers=doctor, data={'body': '你好'}).status_code == 409
    assert client.get('/api/cases', headers=doctor).json[0]['unread'] == 1
    client.post(f'/api/cases/{case_id}/accept', headers=doctor)
    client.get(f'/api/cases/{case_id}/messages', headers=doctor)
    assert client.get('/api/cases', headers=doctor).json[0]['unread'] == 0
    for text in ('第一条', '第二条'):
        assert client.post(f'/api/cases/{case_id}/messages', headers=doctor, data={'body': text}).status_code == 201
    assert client.post(f'/api/cases/{case_id}/messages', headers=headers, data={'body': ''}).status_code == 400
    with_file = client.post(f'/api/cases/{case_id}/messages', headers=headers, data={'attachments': [png()]})
    assert with_file.status_code == 201 and with_file.json['attachments'][0]['name'] == '检查.png'
    messages = client.get(f'/api/cases/{case_id}/messages', headers=headers).json
    assert [m['mine'] for m in messages] == [True, False, False, True]
    patient_id = client.get('/api/auth/me', headers=headers).json['id']
    with app.app_context():
        to_patient = db.session.execute(db.select(Notification).where(
            Notification.kind == 'message', Notification.user_id == patient_id)).scalars().all()
        assert len(to_patient) == 1 and to_patient[0].body == '第二条'  # consecutive messages collapse


def test_message_window_closes_after_completion(client):
    case_id, headers, doctor = accepted_case(client)
    publish(client, case_id, doctor, followup_days=0)
    assert client.post(f'/api/cases/{case_id}/messages', headers=headers, data={'body': '报告看懂了，谢谢'}).status_code == 201
    with app.app_context():
        case = db.session.get(Case, case_id)
        case.published_at = now() - timedelta(days=8)
        db.session.commit()
    closed = client.post(f'/api/cases/{case_id}/messages', headers=headers, data={'body': '还有一个问题'})
    assert closed.status_code == 409 and '复诊' in closed.json['error']


def test_follow_up_visit_links_to_original_case(client):
    case_id, headers, doctor = accepted_case(client)
    published = publish(client, case_id, doctor, followup_days=7)
    assert published['followup_state'] == 'scheduled'
    with app.app_context():
        db.session.get(Case, case_id).followup_due = date.today()
        db.session.commit()
    assert client.get('/api/cases', headers=headers).json[0]['followup_state'] == 'due'
    assert submit(client, headers, parent_id='999').status_code == 400
    revisit = submit(client, headers, parent_id=str(case_id), title='复诊：咳嗽', description='咳嗽好转，但夜间仍有少量干咳。')
    assert revisit.status_code == 201 and revisit.json['kind'] == 'followup' and revisit.json['parent']['id'] == case_id
    assert submit(client, headers, parent_id=str(case_id)).status_code == 400
    original = client.get(f'/api/cases/{case_id}', headers=headers).json
    assert 'followup' not in original['actions'] and original['followup_state'] == 'returned'
    doctor_view = client.get(f'/api/cases/{revisit.json["id"]}', headers=doctor).json
    assert doctor_view['parent']['report']['summary'] == '上呼吸道感染可能'
    assert client.get(f'/api/cases/{revisit.json["id"]}', headers=headers).json['parent']['report'] is None
