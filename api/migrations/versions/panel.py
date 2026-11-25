from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE pasos ADD COLUMN ocultado_por text, ADD COLUMN ocultado_en timestamptz")

def downgrade():
    op.execute("ALTER TABLE pasos DROP COLUMN ocultado_por, DROP COLUMN ocultado_en")
