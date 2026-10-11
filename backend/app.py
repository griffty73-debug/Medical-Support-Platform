import os
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate, stamp, upgrade
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash

from models import AuditLog, User, db
from routes import auth as auth_routes
from routes import cases as case_routes
from security import PHONE, error, password_problem  # noqa: F401  (PHONE is used by scripts)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = Path(__file__).resolve().parent / 'migrations'
load_dotenv(ROOT / '.env')
PLACEHOLDER_SECRET = 'replace-with-a-long-random-secret'
DEFAULT_ORIGINS = 'http://127.0.0.1:5173,http://127.0.0.1:5174,http://localhost:5173,http://localhost:5174'

migrate = Migrate()


def create_app(test_config=None):
    application = Flask(__name__)
    application.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={'pool_pre_ping': True},
        MAX_CONTENT_LENGTH=51 * 1024 * 1024,
        UPLOAD_DIR=str(ROOT / 'backend' / 'uploads'),
        JSON_AS_ASCII=False,
    )
    if test_config:
        application.config.update(test_config)
    secret = application.config['SECRET_KEY']
    if not secret or secret == PLACEHOLDER_SECRET:
        raise RuntimeError('Configure a unique SECRET_KEY in .env')
    if application.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        application.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
    Path(application.config['UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    origins = [o.strip() for o in os.getenv('CORS_ORIGINS', DEFAULT_ORIGINS).split(',') if o.strip()]
    CORS(application, resources={r'/api/*': {'origins': origins}})
    db.init_app(application)
    migrate.init_app(application, db, directory=str(MIGRATIONS))
    application.register_blueprint(auth_routes.bp, url_prefix='/api')
    application.register_blueprint(case_routes.bp, url_prefix='/api')
    auth_routes.register_errors(application)
    register_handlers(application)
    register_commands(application)
    return application


def register_handlers(application):
    @application.errorhandler(HTTPException)
    def handle_http_error(exc):
        messages = {413: '上传总大小超过 50 MB', 404: '内容不存在', 405: '不支持此请求方式'}
        return error(messages.get(exc.code, '请求无效'), exc.code)

    @application.errorhandler(Exception)
    def handle_error(exc):
        db.session.rollback()
        application.logger.exception('Request failed: %s', type(exc).__name__)
        return error('服务暂时异常，请稍后重试', 500)

    @application.after_request
    def secure_response(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @application.get('/api/health')
    def health():
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok', 'database': db.engine.dialect.name})


def register_commands(application):
    @application.cli.command('init-db')
    def init_db_command():
        """Create or upgrade the schema. Databases created by the first version
        (without migration history) are stamped at the baseline first."""
        tables = set(inspect(db.engine).get_table_names())
        if 'alembic_version' not in tables and 'case' in tables:
            stamp(directory=str(MIGRATIONS), revision='0001_baseline')
            click.echo('Existing database detected; marked as baseline schema.')
        upgrade(directory=str(MIGRATIONS))
        click.echo('Database schema is up to date.')

    @application.cli.command('create-doctor')
    @click.option('--name', prompt=True)
    @click.option('--phone', prompt=True)
    @click.option('--department', prompt=True)
    @click.option('--title', default='主治医师', show_default=True)
    @click.option('--specialty', default='')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_doctor(name, phone, department, title, specialty, password):
        if not PHONE.fullmatch(phone):
            raise click.ClickException('Invalid phone number.')
        problem = password_problem(password)
        if problem:
            raise click.ClickException(problem)
        db.session.add(User(name=name, phone=phone, department=department, title=title, specialty=specialty,
                            role='doctor', password_hash=generate_password_hash(password)))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException('Phone already registered.')
        click.echo('Doctor created.')

    @application.cli.command('audit-log')
    @click.option('--case', 'case_id', type=int, help='Only entries for this case id')
    @click.option('--user', 'user_id', type=int, help='Only entries by this user id')
    @click.option('--limit', default=50, show_default=True)
    def audit_log(case_id, user_id, limit):
        """Print recent access and security events."""
        query = db.select(AuditLog, User).outerjoin(User, AuditLog.user_id == User.id).order_by(AuditLog.id.desc())
        if case_id:
            query = query.where(AuditLog.case_id == case_id)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        for log, user in db.session.execute(query.limit(limit)):
            who = f'{user.name}({user.role}#{user.id})' if user else '-'
            case = f'MP-{log.case_id:06d}' if log.case_id else '-'
            click.echo(f'{log.created_at:%Y-%m-%d %H:%M:%S}  {log.action:<24} {case:<10} {who:<24} {log.ip or ""} {log.detail or ""}')


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('FLASK_PORT', '5001')), debug=False, threaded=True)
