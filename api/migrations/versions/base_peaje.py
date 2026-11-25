from pathlib import Path
from alembic import op
revision="0001"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    conn=op.get_bind()
    sql=Path(__file__).resolve().parents[2].joinpath("schema.sql").read_text(encoding="utf-8-sig")
    for statement in sql.split(";"):
        if statement.strip():conn.exec_driver_sql(statement.replace("%","%%"))
