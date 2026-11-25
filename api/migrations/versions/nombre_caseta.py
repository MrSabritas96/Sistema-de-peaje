from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("UPDATE casetas SET nombre='Caseta La Paz' WHERE id=1 AND nombre='Caseta DEMO'")

def downgrade():
    pass
