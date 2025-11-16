from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '001_create_adminlogs'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'AdminLogs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column('admin_id', UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('entity_id', UUID(as_uuid=True)),
        sa.Column('details', JSONB),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    op.create_index('idx_adminlogs_admin_id', 'AdminLogs', ['admin_id'])
    op.create_index('idx_adminlogs_action', 'AdminLogs', ['action'])


def downgrade():
    op.drop_table('AdminLogs')
