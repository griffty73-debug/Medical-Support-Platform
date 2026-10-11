"""Care workflow: triage, messaging, follow-up, report editions, security and audit.

Existing data is carried over:
- Reports on unpublished cases were doctor drafts; they move to ``draft`` and
  ``report`` is cleared so it only ever holds published content.
- Completed cases become published edition 1.
- Accepted time comes from the existing timeline; response deadlines are set for
  waiting cases; existing attachments are attributed to the patient.

Revision ID: 0002_care_workflow
Revises: 0001_baseline
Create Date: 2026-10-09
"""
from datetime import timedelta

from alembic import op
import sqlalchemy as sa

revision = '0002_care_workflow'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    with op.batch_alter_table('user') as table:
        table.add_column(sa.Column('accepting', sa.Boolean(), nullable=False, server_default=sa.true()))
        table.add_column(sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))
        table.add_column(sa.Column('failed_logins', sa.Integer(), nullable=False, server_default='0'))
        table.add_column(sa.Column('locked_until', TS))
        table.add_column(sa.Column('last_login_at', TS))
        table.add_column(sa.Column('password_changed_at', TS))

    with op.batch_alter_table('case') as table:
        table.add_column(sa.Column('kind', sa.String(20), nullable=False, server_default='initial'))
        table.add_column(sa.Column('parent_id', sa.Integer()))
        table.add_column(sa.Column('status_reason', sa.String(500)))
        table.add_column(sa.Column('urgency', sa.String(20), nullable=False, server_default='routine'))
        table.add_column(sa.Column('triage', sa.JSON()))
        table.add_column(sa.Column('answers', sa.JSON()))
        table.add_column(sa.Column('consent_at', TS))
        table.add_column(sa.Column('consent_version', sa.String(20)))
        table.add_column(sa.Column('draft', sa.JSON()))
        table.add_column(sa.Column('published_version', sa.Integer(), nullable=False, server_default='0'))
        table.add_column(sa.Column('ai_draft', sa.JSON()))
        table.add_column(sa.Column('ai_edit_ratio', sa.Float()))
        table.add_column(sa.Column('followup_due', sa.Date()))
        table.add_column(sa.Column('rating', sa.SmallInteger()))
        table.add_column(sa.Column('review', sa.Text()))
        table.add_column(sa.Column('reviewed_at', TS))
        table.add_column(sa.Column('patient_read_at', TS))
        table.add_column(sa.Column('doctor_read_at', TS))
        table.add_column(sa.Column('due_at', TS))
        table.add_column(sa.Column('accepted_at', TS))
        table.add_column(sa.Column('amended_at', TS))
        table.add_column(sa.Column('closed_at', TS))
        table.create_foreign_key('fk_case_parent_id', 'case', ['parent_id'], ['id'])
        table.create_index('ix_case_parent_id', ['parent_id'])
        table.create_index('ix_case_status', ['status'])

    op.create_table(
        'message',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('case.id'), nullable=False),
        sa.Column('sender_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', TS),
    )
    op.create_index('ix_message_case_id', 'message', ['case_id'])

    with op.batch_alter_table('attachment') as table:
        table.add_column(sa.Column('message_id', sa.Integer()))
        table.add_column(sa.Column('uploaded_by', sa.Integer()))
        table.add_column(sa.Column('created_at', TS))
        table.create_foreign_key('fk_attachment_message_id', 'message', ['message_id'], ['id'])
        table.create_foreign_key('fk_attachment_uploaded_by', 'user', ['uploaded_by'], ['id'])
        table.create_index('ix_attachment_message_id', ['message_id'])

    with op.batch_alter_table('case_event') as table:
        table.add_column(sa.Column('actor_id', sa.Integer()))
        table.add_column(sa.Column('detail', sa.Text()))
        table.create_foreign_key('fk_case_event_actor_id', 'user', ['actor_id'], ['id'])

    with op.batch_alter_table('report_history') as table:
        table.add_column(sa.Column('reason', sa.String(500)))

    op.create_table(
        'notification',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('case.id')),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('body', sa.String(300), nullable=False),
        sa.Column('created_at', TS),
        sa.Column('read_at', TS),
    )
    op.create_index('ix_notification_user_id', 'notification', ['user_id'])
    op.create_index('ix_notification_created_at', 'notification', ['created_at'])

    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id')),
        sa.Column('action', sa.String(40), nullable=False),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('case.id')),
        sa.Column('ip', sa.String(64)),
        sa.Column('detail', sa.JSON()),
        sa.Column('created_at', TS),
    )
    op.create_index('ix_audit_log_user_id', 'audit_log', ['user_id'])
    op.create_index('ix_audit_log_case_id', 'audit_log', ['case_id'])
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])

    op.create_table(
        'triage_session',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', TS),
    )
    op.create_index('ix_triage_session_user_id', 'triage_session', ['user_id'])

    _carry_over_data()


def _carry_over_data():
    bind = op.get_bind()
    case = sa.table('case', sa.column('id', sa.Integer), sa.column('patient_id', sa.Integer),
                    sa.column('status', sa.String), sa.column('report', sa.JSON), sa.column('draft', sa.JSON),
                    sa.column('published_version', sa.Integer), sa.column('consent_ai', sa.Boolean),
                    sa.column('consent_at', TS), sa.column('consent_version', sa.String),
                    sa.column('created_at', TS), sa.column('accepted_at', TS), sa.column('due_at', TS),
                    sa.column('triage', sa.JSON))
    event = sa.table('case_event', sa.column('case_id', sa.Integer), sa.column('kind', sa.String),
                     sa.column('created_at', TS))
    attachment = sa.table('attachment', sa.column('case_id', sa.Integer), sa.column('uploaded_by', sa.Integer),
                          sa.column('created_at', TS))
    accepted = dict(bind.execute(sa.select(event.c.case_id, sa.func.min(event.c.created_at))
                                 .where(event.c.kind == 'accepted').group_by(event.c.case_id)).all())
    rows = bind.execute(sa.select(case.c.id, case.c.patient_id, case.c.status, case.c.report,
                                  case.c.consent_ai, case.c.created_at)).all()
    for row in rows:
        values = {'draft': row.report if row.report is not None else sa.null(),
                  'triage': {'level': 'routine', 'flags': [], 'ai': None, 'legacy': True}}
        if row.status == 'completed':
            values['published_version'] = 1
        else:
            values['report'] = sa.null()
        if row.consent_ai:
            values.update(consent_at=row.created_at, consent_version='legacy')
        if row.id in accepted:
            values['accepted_at'] = accepted[row.id]
        if row.status == 'pending' and row.created_at:
            values['due_at'] = row.created_at + timedelta(hours=48)
        bind.execute(case.update().where(case.c.id == row.id).values(**values))
        bind.execute(attachment.update().where(attachment.c.case_id == row.id)
                     .values(uploaded_by=row.patient_id, created_at=row.created_at))


def downgrade():
    case = sa.table('case', sa.column('status', sa.String), sa.column('report', sa.JSON), sa.column('draft', sa.JSON))
    op.execute(case.update().where(case.c.status != 'completed').values(report=case.c.draft))
    for table in ('triage_session', 'audit_log', 'notification'):
        op.drop_table(table)
    with op.batch_alter_table('report_history') as table:
        table.drop_column('reason')
    with op.batch_alter_table('case_event') as table:
        table.drop_constraint('fk_case_event_actor_id', type_='foreignkey')
        table.drop_column('detail')
        table.drop_column('actor_id')
    with op.batch_alter_table('attachment') as table:
        table.drop_index('ix_attachment_message_id')
        table.drop_constraint('fk_attachment_uploaded_by', type_='foreignkey')
        table.drop_constraint('fk_attachment_message_id', type_='foreignkey')
        for column in ('created_at', 'uploaded_by', 'message_id'):
            table.drop_column(column)
    op.drop_table('message')
    with op.batch_alter_table('case') as table:
        table.drop_index('ix_case_status')
        table.drop_index('ix_case_parent_id')
        table.drop_constraint('fk_case_parent_id', type_='foreignkey')
        for column in ('closed_at', 'amended_at', 'accepted_at', 'due_at', 'doctor_read_at', 'patient_read_at',
                       'reviewed_at', 'review', 'rating', 'followup_due', 'ai_edit_ratio', 'ai_draft',
                       'published_version', 'draft', 'consent_version', 'consent_at', 'answers', 'triage',
                       'urgency', 'status_reason', 'parent_id', 'kind'):
            table.drop_column(column)
    with op.batch_alter_table('user') as table:
        for column in ('password_changed_at', 'last_login_at', 'locked_until', 'failed_logins', 'token_version',
                       'accepting'):
            table.drop_column(column)
