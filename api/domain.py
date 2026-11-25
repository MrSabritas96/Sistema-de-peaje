import hashlib
import json
import os
import re
from pathlib import Path

from sqlalchemy import create_engine, text

db = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
CATEGORIES = {"moto", "auto", "minibus", "camion", "bus"}


def init():
    from alembic import command
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option("script_location",str(Path(__file__).with_name("migrations")))
    with db.begin() as conn:
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(808110025)")
        cfg.attributes["connection"]=conn
        command.upgrade(cfg,"head")
        email=os.getenv("INITIAL_ADMIN_EMAIL","").strip().lower()
        if email:
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email):
                raise ValueError("Revisa INITIAL_ADMIN_EMAIL")
            conn.execute(text("INSERT INTO usuarios(email,rol,activo) VALUES (:email,'ADMIN',true) ON CONFLICT DO NOTHING"),{"email":email})


def normalize(value):
    return re.sub(r"[\s-]", "", (value or "").upper())


def query(conn, sql, **params):
    return conn.execute(text(sql), params)


def register(result, booth, direction, operator, session, digest, save_evidence=None):
    plate = normalize(result.get("plate"))
    category, axles = result.get("vehicle_category"), result.get("axles")
    with db.begin() as conn:
        station = query(conn, "SELECT * FROM casetas WHERE activa AND id=:id", id=booth).mappings().first()
        if station is None:
            raise ValueError("Caseta inexistente")
        key = json.dumps([booth, direction])
        query(conn, "SELECT pg_advisory_xact_lock(:key)", key=int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True))
        params = dict(booth=booth, direction=direction, session=session, digest=digest, plate=plate)
        if plate:
            previous = query(conn, """SELECT id FROM pasos WHERE caseta=:booth AND sentido=:direction AND placa=:plate
                AND fecha>=clock_timestamp()-interval '45 seconds' ORDER BY id DESC LIMIT 1""", **params).scalar()
        else:
            previous = query(conn, """SELECT paso FROM detecciones WHERE caseta=:booth AND sentido=:direction AND sesion=:session
                AND operador=:operator AND NULLIF(resultado->>'plate','') IS NULL AND (evidencia=:digest OR bit_count((resultado->>'visual_hash')::bit(64) # CAST(:visual AS bit(64)))<=8)
                AND fecha>=clock_timestamp()-interval '45 seconds' ORDER BY id DESC LIMIT 1""", **params,operator=operator,visual=result.get("visual_hash")).scalar()
        if previous is None and result.get("visual_hash") and plate:
            recent=query(conn,"""SELECT paso, bit_count((resultado->>'vehicle_hash')::bit(64) # CAST(:vehicle AS bit(64))) AS distancia, resultado->>'plate' AS seen FROM detecciones
                WHERE caseta=:booth AND sentido=:direction AND operador=:operator AND sesion=:session
                AND fecha>=clock_timestamp()-interval '12 seconds' AND resultado->>'vehicle_category'=:category
                AND (bit_count((resultado->>'visual_hash')::bit(64) # CAST(:visual AS bit(64)))<=8
                     OR bit_count((resultado->>'vehicle_hash')::bit(64) # CAST(:vehicle AS bit(64)))<=5)
                ORDER BY id DESC LIMIT 3""",**params,operator=operator,category=category,visual=result["visual_hash"],vehicle=result.get("vehicle_hash")).mappings()
            for row in recent:
                seen=row["seen"] or ""
                if (not seen and row["distancia"] is not None and row["distancia"]<=3) or (len(seen)==len(plate) and sum(a!=b for a,b in zip(seen,plate))==1):
                    previous=row["paso"]
                    break
        step = previous
        if previous is None:
            amount = before = after = None
            if not plate:
                state = "ERROR_OCR" if result.get("plate_bbox") else "SIN_PLACA"
            elif (not re.fullmatch(r"[0-9]{3,4}[A-Z]{3}", plate) or result.get("review_required", True)
                  or category not in CATEGORIES or type(axles) is not int or not 2 <= axles <= 8):
                state = "REVISION_MANUAL"
            else:
                vehicle = query(conn, "SELECT saldo FROM vehiculos WHERE activo AND placa=:plate FOR UPDATE", plate=plate).first()
                if vehicle is None:
                    state = "IDENTIFICADA_NO_REGISTRADA"
                else:
                    amount = query(conn, "SELECT monto FROM tarifas WHERE categoria=:c AND ejes=:a", c=category, a=axles).scalar()
                    before = after = vehicle.saldo
                    if amount is None:
                        state = "TARIFA_NO_CONFIGURADA"
                    elif before < amount:
                        state = "SIN_SALDO"
                    else:
                        state = "PAGADO"
                        after = before - amount
                        query(conn, "UPDATE vehiculos SET saldo=:after WHERE placa=:plate", after=after, plate=plate)
            origin, destination = station["origen"], station["destino"]
            if direction == "SALIDA":
                origin, destination = destination, origin
            step = query(conn, """INSERT INTO pasos(placa,categoria,ejes,monto,saldo_anterior,saldo_posterior,estado,
                caseta,sentido,origen,destino,operador,evidencia) VALUES (:plate,:c,:a,:amount,:before,:after,:state,
                :booth,:direction,:origin,:destination,:operator,:digest) RETURNING id""", **params,c=category,a=axles,
                amount=amount,before=before,after=after,state=state,origin=origin,destination=destination,operator=operator).scalar_one()
            if state != "PAGADO":
                query(conn, "INSERT INTO alertas(paso,tipo) VALUES (:step,:state)", step=step,state=state)
        if previous is not None and save_evidence is not None:
            record=dict(query(conn,"SELECT * FROM pasos WHERE id=:step",step=step).mappings().one())
            compatible = all(old is None or old == new for old,new in (
                (record["placa"] or None,plate or None),(record["categoria"],category),(record["ejes"],axles)))
            improved = any(not old and new for old,new in (
                (record["placa"],plate),(record["categoria"],category),(record["ejes"],axles)))
            if not (record["estado"] in {"SIN_PLACA","ERROR_OCR","REVISION_MANUAL"} and compatible and improved):
                return dict(record,duplicada=True)
            state = "REVISION_MANUAL" if plate else record["estado"]
            query(conn,"UPDATE pasos SET placa=NULLIF(:plate,''),categoria=:c,ejes=:a,evidencia=:digest,estado=:state WHERE id=:step",
                  **params,c=category,a=axles,state=state,step=step)
            query(conn,"UPDATE alertas SET tipo=:state WHERE paso=:step",state=state,step=step)
        if save_evidence is not None:
            save_evidence()
        query(conn, """INSERT INTO detecciones(paso,operador,caseta,sentido,sesion,evidencia,resultado,duplicada)
              VALUES (:step,:operator,:booth,:direction,:session,:digest,CAST(:result AS jsonb),:duplicate)""",
              **params,step=step,operator=operator,result=json.dumps(result,allow_nan=False),duplicate=previous is not None)
        if previous is None or save_evidence is not None:
            query(conn,"UPDATE pasos SET pasajeros=:n, placa_leida=:raw, confianza_ocr=:confidence WHERE id=:step",
                  n=result.get("pasajeros"),raw=result.get("plate_raw"),confidence=result.get("ocr_confidence"),step=step)
        record = dict(query(conn,"SELECT * FROM pasos WHERE id=:step",step=step).mappings().one())
        return dict(record,duplicada=previous is not None)

