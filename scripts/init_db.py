"""Create an isolated local PostgreSQL cluster without changing existing databases."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATA = ROOT / '.local' / 'postgres'
DATA.parent.mkdir(exist_ok=True)
url = os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://')
params = psycopg.conninfo.conninfo_to_dict(url)
port = params.get('port', '5433')
if not shutil.which('initdb'):
    raise SystemExit('PostgreSQL tools are missing. Install PostgreSQL 16 or use docker compose.')
if not (DATA / 'PG_VERSION').exists():
    with tempfile.NamedTemporaryFile(mode='w') as password_file:
        password_file.write(params['password'])
        password_file.flush()
        subprocess.run(['initdb', '-D', str(DATA), '-U', params['user'],
                        '--encoding=UTF8', '--locale=C', '--auth=scram-sha-256',
                        '--pwfile', password_file.name], check=True)
status = subprocess.run(['pg_ctl', '-D', str(DATA), 'status'], capture_output=True)
if status.returncode:
    subprocess.run(['pg_ctl', '-D', str(DATA), '-l', str(DATA.parent / 'postgres.log'),
                    '-o', f'-p {port} -h 127.0.0.1', 'start'], check=True)
params['dbname'] = 'postgres'
with psycopg.connect(**params, autocommit=True) as conn:
    if not conn.execute('SELECT 1 FROM pg_database WHERE datname = %s', ('medical_treatment',)).fetchone():
        conn.execute('CREATE DATABASE medical_treatment')
print(f'PostgreSQL ready: medical_treatment on 127.0.0.1:{port}, user {params["user"]}')
