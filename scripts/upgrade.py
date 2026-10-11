"""Back up the database, then bring its schema up to date.

Run after pulling a new version:
    .venv/bin/pip install -r backend/requirements.txt
    .venv/bin/python scripts/upgrade.py
    .venv/bin/python scripts/dev.py stop && .venv/bin/python scripts/dev.py start

The backup is a plain SQL dump in .local/backups/. To roll back:
    psql "postgresql://USER:PASSWORD@HOST:PORT/postgres" -c "DROP DATABASE medical_treatment" -c "CREATE DATABASE medical_treatment"
    psql "postgresql://USER:PASSWORD@HOST:PORT/medical_treatment" -f .local/backups/<file>.sql
and restore the previous source files.
"""
import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--skip-backup', action='store_true', help='Upgrade without a backup (not recommended)')
args = parser.parse_args()

url = os.environ['DATABASE_URL']
backups = ROOT / '.local' / 'backups'
backups.mkdir(parents=True, exist_ok=True)

if url.startswith('postgresql') and not args.skip_backup:
    target = backups / f'medical_treatment-{datetime.now():%Y%m%d-%H%M%S}.sql'
    plain = url.replace('postgresql+psycopg://', 'postgresql://')
    if shutil.which('pg_dump'):
        command = ['pg_dump', '--no-owner', '--file', str(target), plain]
    elif shutil.which('docker'):
        command = ['docker', 'compose', 'exec', '-T', 'postgres', 'pg_dump', '--no-owner', '-U', 'postgres', 'medical_treatment']
    else:
        raise SystemExit('pg_dump was not found. Install the PostgreSQL 16 command-line tools, or rerun with --skip-backup.')
    print('Backing up database …')
    if command[0] == 'docker':
        with target.open('wb') as output:
            subprocess.run(command, cwd=ROOT, stdout=output, check=True)
    else:
        subprocess.run(command, check=True)
    target.chmod(0o600)
    print(f'Backup written: {target.relative_to(ROOT)} ({target.stat().st_size // 1024} KB)')

print('Upgrading schema …')
result = subprocess.run([sys.executable, '-m', 'flask', '--app', str(ROOT / 'backend' / 'app.py'), 'init-db'], cwd=ROOT)
if result.returncode:
    raise SystemExit('Upgrade failed; the database was not changed beyond the failed transaction. The backup above is intact.')
print('Done. Restart the services: .venv/bin/python scripts/dev.py stop && .venv/bin/python scripts/dev.py start')
