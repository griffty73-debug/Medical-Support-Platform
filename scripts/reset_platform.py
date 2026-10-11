"""Reset this project's local data and create one doctor using a hidden password prompt."""
import argparse
from getpass import getpass
from pathlib import Path
import sys

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app import app, PHONE
from models import (Attachment, AuditLog, Case, CaseEvent, Message, Notification, ReportHistory, TriageSession,
                    User, db)
from security import password_problem

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--doctor-phone', required=True)
parser.add_argument('--doctor-name', default='接诊医生')
parser.add_argument('--department', default='医疗咨询')
args = parser.parse_args()
if not PHONE.fullmatch(args.doctor_phone):
    raise SystemExit('Invalid doctor phone.')
password = getpass('Doctor password: ')
problem = password_problem(password)
if problem:
    raise SystemExit(problem)

with app.app_context():
    url = db.engine.url
    if (url.host, url.port, url.database) != ('127.0.0.1', 5433, 'medical_treatment'):
        raise SystemExit('This reset is restricted to the project database on port 5433.')
    if input('This deletes every patient, case, message and audit record. Type RESET to continue: ') != 'RESET':
        raise SystemExit('Cancelled.')
    for model in (Notification, AuditLog, TriageSession, Attachment, Message, ReportHistory, CaseEvent):
        db.session.execute(db.delete(model))
    db.session.execute(db.update(Case).values(parent_id=None))
    db.session.execute(db.delete(Case))
    db.session.execute(db.delete(User))
    # Sequences are preserved so tokens belonging to deleted users cannot match the new doctor.
    db.session.add(User(name=args.doctor_name, phone=args.doctor_phone, role='doctor', department=args.department,
                        title='医生', specialty='', password_hash=generate_password_hash(password)))
    db.session.commit()
    assert db.session.query(User).count() == 1 and db.session.query(Case).count() == 0
    response = app.test_client().post('/api/auth/login', json={'phone': args.doctor_phone, 'password': password, 'role': 'doctor'})
    assert response.status_code == 200, response.json
    for path in Path(app.config['UPLOAD_DIR']).iterdir():
        if path.is_file() and path.name != '.gitkeep':
            path.unlink()
print('Reset complete: one doctor, no patients, cases, messages, attachments or audit records. Login verified.')
