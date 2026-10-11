from io import BytesIO

from pypdf import PdfReader
from reportlab.pdfgen import canvas

import routes.cases as case_routes
from app import app
from conftest import (accepted_case, full_report, login_doctor, patient, png, publish, register, submit)
from models import Case, Notification, ReportHistory, db


def actions(client, case_id, headers):
    return set(client.get(f'/api/cases/{case_id}', headers=headers).json['actions'])


def test_submission_requires_complete_profile_and_explicit_consent(client):
    headers = register(client)
    assert submit(client, headers).status_code == 422
    headers = patient(client, '13800000002')
    assert submit(client, headers, consent_share='false').status_code == 400
    assert submit(client, headers, doctor_id='3').status_code == 400  # doctor paused
    response = submit(client, headers, consent_ai='false')
    assert response.status_code == 201
    assert response.json['consent_ai'] is False and response.json['status'] == 'pending'
    assert response.json['due_at'] and response.json['urgency'] == 'routine'


def test_full_flow_with_info_request_supplement_publish_and_amend(client):
    case_id, patient_headers, doctor = accepted_case(client)
    assert actions(client, case_id, doctor) >= {'request_info', 'edit_draft', 'publish', 'decline', 'transfer', 'message'}
    assert actions(client, case_id, patient_headers) == {'cancel', 'message'}

    assert client.post(f'/api/cases/{case_id}/request-info', headers=doctor, json={'message': '短'}).status_code == 400
    asked = client.post(f'/api/cases/{case_id}/request-info', headers=doctor, json={'message': '请上传最近一次血常规结果'})
    assert asked.json['status'] == 'awaiting_info'
    assert 'publish' not in asked.json['actions']
    assert 'supplement' in actions(client, case_id, patient_headers)
    supplemented = client.post(f'/api/cases/{case_id}/supplement', headers=patient_headers,
                               data={'body': '已上传血常规', 'attachments': [png('血常规.png')]})
    assert supplemented.status_code == 200 and supplemented.json['status'] == 'processing'
    assert supplemented.json['attachments'][0]['message_id'] is not None

    saved = client.put(f'/api/cases/{case_id}/draft', headers=doctor,
                       json={'version': 0, 'report': {'summary': '草稿', 'basis': '', 'treatment': '', 'advice': ''}})
    assert saved.status_code == 200 and saved.json['report_version'] == 1
    stale = client.put(f'/api/cases/{case_id}/draft', headers=doctor, json={'version': 0, 'report': full_report()})
    assert stale.status_code == 409
    seen_by_patient = client.get(f'/api/cases/{case_id}', headers=patient_headers).json
    assert 'report' not in seen_by_patient and 'draft' not in seen_by_patient
    assert client.get(f'/api/cases/{case_id}/report/pdf', headers=patient_headers).status_code == 409

    incomplete = client.post(f'/api/cases/{case_id}/publish', headers=doctor,
                             json={'version': 1, 'report': full_report(visit=None), 'confirmed': True})
    assert incomplete.status_code == 400 and '线下就诊' in incomplete.json['error']
    unconfirmed = client.post(f'/api/cases/{case_id}/publish', headers=doctor,
                              json={'version': 1, 'report': full_report()})
    assert unconfirmed.status_code == 400
    published = publish(client, case_id, doctor)
    assert published['status'] == 'completed' and published['published_version'] == 1
    assert published['followup_due'] and published['ai_edit_ratio'] is None

    seen = client.get(f'/api/cases/{case_id}', headers=patient_headers).json
    assert seen['report']['basis'] == '咳嗽三天，无发热' and 'review' in seen['actions']
    pdf = client.get(f'/api/cases/{case_id}/report/pdf', headers=patient_headers)
    text = PdfReader(BytesIO(pdf.data)).pages[0].extract_text()
    assert '测试患者' in text and '随访' in text and b'/FontFile2' in pdf.data

    no_change = client.post(f'/api/cases/{case_id}/amend', headers=doctor, json={
        'published_version': 1, 'report': full_report(), 'reason': '修正用语', 'confirmed': True})
    assert no_change.status_code == 400
    no_reason = client.post(f'/api/cases/{case_id}/amend', headers=doctor, json={
        'published_version': 1, 'report': full_report(advice='新的注意事项'), 'reason': '', 'confirmed': True})
    assert no_reason.status_code == 400
    amended = client.post(f'/api/cases/{case_id}/amend', headers=doctor, json={
        'published_version': 1, 'report': full_report(advice='新的注意事项', followup_days=14),
        'reason': '补充随访时间', 'confirmed': True})
    assert amended.status_code == 200 and amended.json['published_version'] == 2
    assert client.post(f'/api/cases/{case_id}/amend', headers=doctor, json={
        'published_version': 1, 'report': full_report(advice='再改'), 'reason': '并发修改', 'confirmed': True}).status_code == 409
    seen = client.get(f'/api/cases/{case_id}', headers=patient_headers).json
    assert seen['report']['advice'] == '新的注意事项' and seen['status_reason'] == '补充随访时间'
    history = client.get(f'/api/cases/{case_id}/report/history', headers=doctor).json
    assert [h['action'] for h in history] == ['amended', 'published', 'saved']
    assert client.get(f'/api/cases/{case_id}/report/history', headers=patient_headers).status_code == 403

    reviewed = client.post(f'/api/cases/{case_id}/review', headers=patient_headers, json={'rating': 5, 'review': '解释清楚'})
    assert reviewed.status_code == 200 and 'review' not in reviewed.json['actions']
    assert client.post(f'/api/cases/{case_id}/review', headers=patient_headers, json={'rating': 4}).status_code == 409
    directory = client.get('/api/doctors', headers=patient_headers).json
    assert directory[0]['rating'] == 5.0 and directory[0]['rating_count'] == 1
    with app.app_context():
        kinds = [n.kind for n in db.session.execute(db.select(Notification).order_by(Notification.id)).scalars()]
        assert kinds[:3] == ['new_case', 'accepted', 'info_requested']
        assert {'supplemented', 'published', 'amended', 'reviewed'} <= set(kinds)


def test_decline_then_reassign_moves_access(client):
    headers = patient(client)
    case_id = submit(client, headers).json['id']
    first, second = login_doctor(client, 1), login_doctor(client, 2)
    assert client.get(f'/api/cases/{case_id}', headers=second).status_code == 404
    assert client.post(f'/api/cases/{case_id}/decline', headers=first, json={'reason': ''}).status_code == 400
    declined = client.post(f'/api/cases/{case_id}/decline', headers=first, json={'reason': '需要呼吸专科评估'})
    assert declined.json['status'] == 'declined'
    seen = client.get(f'/api/cases/{case_id}', headers=headers).json
    assert seen['status_reason'] == '需要呼吸专科评估' and {'reassign', 'cancel'} <= set(seen['actions'])
    assert client.post(f'/api/cases/{case_id}/reassign', headers=headers, json={'doctor_id': 1}).status_code == 400
    assert client.post(f'/api/cases/{case_id}/reassign', headers=headers, json={'doctor_id': 3}).status_code == 400
    moved = client.post(f'/api/cases/{case_id}/reassign', headers=headers, json={'doctor_id': 2})
    assert moved.status_code == 200 and moved.json['status'] == 'pending' and moved.json['doctor']['id'] == 2
    assert client.get(f'/api/cases/{case_id}', headers=first).status_code == 404
    assert client.post(f'/api/cases/{case_id}/accept', headers=second).status_code == 200
    assert client.post(f'/api/cases/{case_id}/accept', headers=second).status_code == 409


def test_transfer_clears_draft_and_hands_over(client):
    case_id, headers, first = accepted_case(client)
    client.put(f'/api/cases/{case_id}/draft', headers=first, json={'version': 0, 'report': full_report()})
    assert client.post(f'/api/cases/{case_id}/transfer', headers=first, json={'doctor_id': 3, 'reason': '转皮肤科'}).status_code == 400
    moved = client.post(f'/api/cases/{case_id}/transfer', headers=first, json={'doctor_id': 2, 'reason': '需呼吸科进一步评估'})
    assert moved.status_code == 200 and moved.json['transferred']
    assert client.get(f'/api/cases/{case_id}', headers=first).status_code == 404
    second = login_doctor(client, 2)
    detail = client.get(f'/api/cases/{case_id}', headers=second).json
    assert detail['status'] == 'pending' and detail['draft'] is None and detail['events'][-1]['kind'] == 'transferred'


def test_cancel_rules(client):
    case_id, headers, doctor = accepted_case(client)
    cancelled = client.post(f'/api/cases/{case_id}/cancel', headers=headers, json={'reason': '已线下就诊'})
    assert cancelled.json['status'] == 'cancelled' and cancelled.json['actions'] == []
    assert client.post(f'/api/cases/{case_id}/accept', headers=doctor).status_code == 409
    with app.app_context():
        assert db.session.execute(db.select(Notification).where(Notification.kind == 'cancelled')).scalar()
    other, headers2, doctor2 = accepted_case(client, patient(client, '13800000002'))
    publish(client, other, doctor2)
    assert client.post(f'/api/cases/{other}/cancel', headers=headers2, json={}).status_code == 409


def test_permissions_and_masked_identity(client):
    headers = patient(client)
    case_id = submit(client, headers).json['id']
    stranger = patient(client, '13800000002')
    assert client.get(f'/api/cases/{case_id}', headers=stranger).status_code == 404
    assert client.get(f'/api/cases/{case_id}', headers=login_doctor(client, 2)).status_code == 404
    assert client.post(f'/api/cases/{case_id}/accept', headers=headers).status_code == 403
    assert client.get('/api/cases').status_code == 401
    doctor = login_doctor(client)
    detail = client.get(f'/api/cases/{case_id}', headers=doctor).json
    assert 'national_id' not in detail['profile'] and '*' in detail['profile']['national_id_masked']
    assert detail['profile']['phone'] == '138****0001'
    assert client.get(f'/api/cases/{case_id}', headers=headers).json['profile']['phone'] == '13800000001'
    assert len(client.post(f'/api/cases/{case_id}/reveal-id', headers=doctor).json['national_id']) == 18
    log = client.get(f'/api/cases/{case_id}/access-log', headers=headers).json
    assert {'case_viewed', 'national_id_revealed'} <= {entry['action'] for entry in log}


def test_upload_validation_and_attachment_access(client):
    headers = patient(client)
    assert submit(client, headers, attachments=[(BytesIO(b'bad'), 'scan.exe')]).status_code == 400
    assert submit(client, headers, attachments=[(BytesIO(b'bad'), 'fake.png')]).status_code == 400
    assert submit(client, headers, attachments=[png(f'{i}.png') for i in range(6)]).status_code == 400
    response = submit(client, headers, attachments=[png()])
    assert response.status_code == 201
    attachment_id = response.json['attachments'][0]['id']
    assert client.get(f'/api/attachments/{attachment_id}', headers=headers).status_code == 200
    assert client.get(f'/api/attachments/{attachment_id}', headers=login_doctor(client)).status_code == 200
    assert client.get(f'/api/attachments/{attachment_id}', headers=patient(client, '13800000002')).status_code == 404
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(50, 700, 'Synthetic laboratory report')
    pdf.save()
    stream.seek(0)
    assert submit(client, headers, attachments=[(stream, '检查.pdf')]).json['attachments'][0]['mime'] == 'application/pdf'
    assert submit(client, headers, attachments=[(BytesIO(b'%PDF-invalid'), '损坏.pdf')]).status_code == 400


def test_ai_draft_respects_consent_and_tracks_edits(client, monkeypatch):
    no_ai, headers, doctor = accepted_case(client, consent_ai='false')
    assert 'ai_draft' not in actions(client, no_ai, doctor)
    assert client.post(f'/api/cases/{no_ai}/ai', headers=doctor, json={'version': 0}).status_code == 409

    case_id, headers, doctor = accepted_case(client, headers)
    draft = full_report(summary='AI 初步评估', basis='AI 依据', treatment='AI 处理', advice='AI 注意事项')
    monkeypatch.setattr(case_routes.ai, 'draft_report', lambda case, conversation: (draft, 'test-qwen'))
    generated = client.post(f'/api/cases/{case_id}/ai', headers=doctor, json={'version': 0})
    assert generated.status_code == 200 and generated.json['draft']['summary'] == 'AI 初步评估'
    assert generated.json['ai_model'] == 'test-qwen' and generated.json['status'] == 'processing'
    assert 'draft' not in client.get(f'/api/cases/{case_id}', headers=headers).json
    published = publish(client, case_id, doctor, summary='医生重写的评估')
    assert 0 < published['ai_edit_ratio'] < 1
    with app.app_context():
        actions_logged = [h.action for h in db.session.execute(db.select(ReportHistory).where(
            ReportHistory.case_id == case_id)).scalars()]
        assert actions_logged == ['ai_generated', 'published']


def test_snapshot_preserves_health_information_at_submission(client):
    headers = patient(client)
    case_id = submit(client, headers).json['id']
    client.put('/api/profile', headers=headers, json={'name': '测试患者', 'allergies': '新增过敏信息', 'medications': '无'})
    assert client.get(f'/api/cases/{case_id}', headers=headers).json['profile']['allergies'] == '青霉素'
    with app.app_context():
        case = db.session.get(Case, case_id)
        assert 'national_id' not in case.profile_snapshot and case.profile_snapshot['age'] >= 30
