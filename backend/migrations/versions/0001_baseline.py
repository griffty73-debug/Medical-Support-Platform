"""Baseline: the schema created by the first release with db.create_all().

Existing databases are stamped at this revision by `flask init-db` instead of
running it, so their data is untouched.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('phone', sa.String(20), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('role', sa.String(10), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('age', sa.Integer()),
        sa.Column('gender', sa.String(10)),
        sa.Column('national_id_encrypted', sa.Text()),
        sa.Column('allergies', sa.Text()),
        sa.Column('history', sa.Text()),
        sa.Column('medications', sa.Text()),
        sa.Column('department', sa.String(60)),
        sa.Column('title', sa.String(60)),
        sa.Column('specialty', sa.Text()),
        sa.Column('avatar', sa.String(200)),
        sa.Column('created_at', TS),
    )
    op.create_table(
        'case',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('doctor_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('duration', sa.String(100)),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('profile_snapshot', sa.JSON(), nullable=False),
        sa.Column('consent_ai', sa.Boolean(), nullable=False),
        sa.Column('report', sa.JSON()),
        sa.Column('report_version', sa.Integer(), nullable=False),
        sa.Column('ai_model', sa.String(100)),
        sa.Column('ai_generated_at', TS),
        sa.Column('created_at', TS),
        sa.Column('updated_at', TS),
        sa.Column('published_at', TS),
    )
    op.create_index('ix_case_patient_id', 'case', ['patient_id'])
    op.create_index('ix_case_doctor_id', 'case', ['doctor_id'])
    op.create_table(
        'attachment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('case.id'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('storage_name', sa.String(100), nullable=False),
        sa.Column('mime', sa.String(80), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
    )
    op.create_index('ix_attachment_case_id', 'attachment', ['case_id'])
    op.create_table(
        'case_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('case.id'), nullable=False),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('message', sa.String(200), nullable=False),
        sa.Column('created_at', TS),
    )
    op.create_index('ix_case_event_case_id', 'case_event', ['case_id'])
    op.create_table(
        'report_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('case.id'), nullable=False),
        sa.Column('doctor_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('created_at', TS),
    )
    op.create_index('ix_report_history_case_id', 'report_history', ['case_id'])


def downgrade():
    for table in ('report_history', 'case_event', 'attachment', 'case', 'user'):
        op.drop_table(table)
