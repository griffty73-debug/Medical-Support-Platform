"""Start or stop this project's development services, with logs in .local/."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
STATE = ROOT / '.local'
STATE.mkdir(exist_ok=True)
PID_FILE = STATE / 'services.json'
parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['start', 'stop', 'status'], default='start', nargs='?')
args = parser.parse_args()
services = json.loads(PID_FILE.read_text()) if PID_FILE.exists() else {}


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


if args.action == 'stop':
    for name, service in services.items():
        if alive(service['pid']):
            os.killpg(service['pid'], signal.SIGTERM)
            print(f'Stopped {name}')
    PID_FILE.unlink(missing_ok=True)
    sys.exit()

specs = [
    ('backend', int(os.getenv('FLASK_PORT', '5001')), [str(ROOT / '.venv' / 'bin' / 'python'), 'backend/app.py'], ROOT),
    ('patient', int(os.getenv('PATIENT_PORT', '5173')), ['npm', 'run', 'dev:patient', '--', '--port', os.getenv('PATIENT_PORT', '5173')], ROOT / 'frontend'),
    ('doctor', int(os.getenv('DOCTOR_PORT', '5174')), ['npm', 'run', 'dev:doctor', '--', '--port', os.getenv('DOCTOR_PORT', '5174')], ROOT / 'frontend'),
]
for name, port, command, cwd in specs:
    if args.action == 'status':
        print(f'{name}: {"running" if name in services and alive(services[name]["pid"]) else "stopped"}')
        continue
    if name in services and alive(services[name]['pid']):
        print(f'{name} already running at http://127.0.0.1:{services[name]["port"]}')
        continue
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            raise SystemExit(f'Port {port} is occupied. Change the corresponding port in .env before starting.')
    with (STATE / f'{name}.log').open('a') as log:
        process = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=log, start_new_session=True)
    services[name] = {'pid': process.pid, 'port': port}
    PID_FILE.write_text(json.dumps(services))
    print(f'{name}: http://127.0.0.1:{port}')
