from alembic import op

revision="0005"
down_revision="0004"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE pasos ADD COLUMN pasajeros integer CHECK(pasajeros >= 0), ADD COLUMN placa_leida text, ADD COLUMN confianza_ocr double precision")
    op.execute("ALTER TABLE usuarios ADD COLUMN id bigserial UNIQUE, ADD COLUMN nombre text")
    op.execute("ALTER TABLE vehiculos ADD COLUMN id bigserial UNIQUE, ADD COLUMN propietario text, ADD COLUMN ejes integer CHECK(ejes>0)")
    op.execute("ALTER TABLE casetas ADD COLUMN ubicacion text")

def downgrade():
    op.execute("ALTER TABLE casetas DROP COLUMN ubicacion")
    op.execute("ALTER TABLE vehiculos DROP COLUMN ejes, DROP COLUMN propietario, DROP COLUMN id")
    op.execute("ALTER TABLE usuarios DROP COLUMN nombre, DROP COLUMN id")
    op.execute("ALTER TABLE pasos DROP COLUMN confianza_ocr, DROP COLUMN placa_leida, DROP COLUMN pasajeros")
