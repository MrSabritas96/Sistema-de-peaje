from alembic import op
revision="0002"
down_revision="0001"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE vehiculos ADD COLUMN IF NOT EXISTS activo boolean NOT NULL DEFAULT true")
    op.execute("ALTER TABLE casetas ADD COLUMN IF NOT EXISTS activa boolean NOT NULL DEFAULT true")
