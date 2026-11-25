from alembic import op
revision="0003"
down_revision="0002"
branch_labels=None
depends_on=None

def upgrade():
    # Replace only the original lab defaults, preserving edited tariffs and paid steps.
    op.execute("""UPDATE tarifas SET monto=(CASE categoria WHEN 'moto' THEN 1 WHEN 'auto' THEN 2
        WHEN 'minibus' THEN 3 WHEN 'bus' THEN 4 WHEN 'camion' THEN 5 END)+(ejes-2)
        WHERE categoria IN ('moto','auto','minibus','bus','camion') AND monto=10*ejes""")
