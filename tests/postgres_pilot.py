"""Run against a fresh PostgreSQL cluster, isolated from existing databases."""
import concurrent.futures
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
pg = Path(os.getenv("PG_BIN", "C:/Program Files/PostgreSQL/18/bin"))
with tempfile.TemporaryDirectory(prefix="peaje_test_") as folder:
    base = Path(folder)
    password = secrets.token_hex(24)
    pwd = base / "password"
    pwd.write_text(password)
    data = base / "data"
    subprocess.run([pg/"initdb", "-D", data, "-U", "laboratorio", "-A", "scram-sha-256", "--pwfile", pwd, "--encoding=UTF8","--locale=C"],check=True,stdout=subprocess.DEVNULL)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    subprocess.run([pg/"pg_ctl","-D",data,"-l",base/"postgres.log","-o",f"-h 127.0.0.1 -p {port}","-w","start"],check=True)
    try:
        os.environ["DATABASE_URL"]=f"postgresql+psycopg://laboratorio:{password}@127.0.0.1:{port}/postgres"
        os.environ["INITIAL_ADMIN_EMAIL"]="alumno@example.invalid"
        from api.domain import db,init,query,register
        init()
        init()
        with db.connect() as conn:
            assert query(conn,"select rol from usuarios where email='alumno@example.invalid'").scalar()=="ADMIN"
            assert query(conn,"select count(*) from vehiculos where is_demo").scalar()==20
        operator="doc.alvaro.pinto.ma@unifranz.edu.bo"
        result=dict(plate="8002-TST",vehicle_category="auto",axles=2,review_required=False)
        def run(data, direction="ENTRADA"):
            return register(data,1,direction,operator,"test","a"*64)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            steps=list(pool.map(run,[result]*6))
        assert len({s["id"] for s in steps})==1 and sum(not s["duplicada"] for s in steps)==1
        assert steps[0]["saldo_posterior"]==98 and steps[0]["estado"]=="PAGADO"
        assert run(result,"SALIDA")["saldo_posterior"]==96
        for patch,expected in [({"plate":"8004TST","vehicle_category":"camion","axles":3},"SIN_SALDO"),({"plate":"9999ZZZ"},"IDENTIFICADA_NO_REGISTRADA"),
                ({"plate":"8001TST","review_required":True},"REVISION_MANUAL"),({"plate":None},"SIN_PLACA")]:
            actual = run(result|patch)["estado"]
            assert actual==expected, (patch,actual,expected)
        with db.connect() as conn:
            assert query(conn,"select count(*) from alertas").scalar()==4
            assert query(conn,"select count(*) from detecciones").scalar()==11
        os.environ["JWT_SECRET"]=secrets.token_hex(32)
        from api.main import app
        from fastapi.testclient import TestClient
        from datetime import datetime,timedelta,timezone
        import jwt
        from PIL import Image
        import io
        token=jwt.encode({"sub":operator,"exp":datetime.now(timezone.utc)+timedelta(minutes=1)},os.environ["JWT_SECRET"],algorithm="HS256")
        headers={"Authorization":"Bearer "+token}
        with TestClient(app) as client:
            assert client.get("/api/v1/health").status_code==200
            assert client.get("/api/v1/historial").status_code==401
            for plate,state in [("8002TST","REGISTRADA_Y_CON_PASO"),("8003TST","REGISTRADA_SIN_PASO"),("9999ZZZ","IDENTIFICADA_NO_REGISTRADA"),("9999XXX","NO_EXISTE")]:
                assert client.get("/api/v1/consulta/"+plate,headers=headers).json()["estado"]==state
            jpg=io.BytesIO()
            Image.new("RGB",(16,16)).save(jpg,format="JPEG")
            frm={"caseta":"1","sentido":"ENTRADA","sesion":"test"}
            assert client.post("/api/v1/pasos/frame",headers=headers,data=frm,files={"file":("test.jpg",b"bad","image/jpeg")}).status_code==422
            assert client.post("/api/v1/pasos/frame",headers=headers,data=frm,files={"file":("test.jpg",jpg.getvalue(),"image/jpeg")}).status_code==503
            assert client.put("/api/v1/tarifas",headers=headers,json={"categoria":"auto","ejes":2,"monto":19}).status_code==200
            assert client.get("/api/v1/admin/vehiculos",headers=headers).status_code==200
            assert client.get("/api/v1/alertas",headers=headers).status_code==200
            suggestion=client.post("/api/v1/chat",headers=headers,json={"pregunta":"8O02-TST"}).json()
            assert "8002TST" in suggestion["sugerencias"] and "caseta" in suggestion["respuesta"]
            manual=next(s for s in client.get("/api/v1/historial",headers=headers).json() if s["estado"]=="REVISION_MANUAL")
            correction={"placa":"8001TST","categoria":"moto","ejes":2,"motivo":"Confirmado en evidencia de prueba DEMO"}
            route="/api/v1/pasos/"+str(manual["id"])+"/confirmar"
            assert client.post(route,headers=headers,json=correction).json()["estado"]=="PAGADO"
            assert client.post(route,headers=headers,json=correction).status_code==409
            hidden_id=manual["id"]
            hide=f"/api/v1/pasos/{hidden_id}/ocultar"
            assert client.post(hide).status_code==401
            assert client.post(hide,headers=headers).status_code==200
            assert client.post(hide,headers=headers).status_code==200
            assert all(row["id"]!=hidden_id for row in client.get("/api/v1/historial",headers=headers).json())
            with db.connect() as conn:
                assert query(conn,"SELECT monto FROM pasos WHERE id=:id AND estado='PAGADO'",id=hidden_id).scalar()>0
            (root/"docs"/"openapi.json").write_text(__import__("json").dumps(app.openapi(),ensure_ascii=False,indent=2),encoding="utf8")
        from http_flow import check
        check(app,headers,base)
        frame_data=dict(vehicle_category="minibus",axles=2,visual_hash="10"*32,vehicle_hash="01"*32)
        saved=[]
        def capture(data,digest):
            return register(data,1,"ENTRADA",operator,"seleccion",digest,lambda:saved.append(digest))
        early=capture(frame_data,"b"*64)
        improved=capture(dict(frame_data,plate="4321ABC"),"c"*64)
        repeated=capture(dict(frame_data,plate="4321ABC"),"d"*64)
        assert early["id"]==improved["id"]==repeated["id"]
        assert repeated["placa"]=="4321ABC" and repeated["evidencia"]=="c"*64
        assert len(saved)==2
        print("PASS mejor evidencia por paso sin guardar la tercera captura")
        pg_env={**os.environ,"PGPASSWORD":password,"PGHOST":"127.0.0.1","PGPORT":str(port),"PGUSER":"laboratorio"}
        backup=base/"test.dump"
        subprocess.run([pg/"pg_dump","-Fc","-d","postgres","-f",backup],env=pg_env,check=True)
        subprocess.run([pg/"createdb","restauracion"],env=pg_env,check=True)
        subprocess.run([pg/"pg_restore","--exit-on-error","-d","restauracion",backup],env=pg_env,check=True)
        sql="SELECT count(*) FROM vehiculos WHERE is_demo"
        restored=subprocess.check_output([pg/"psql","-At","-d","restauracion","-c",sql],env=pg_env,text=True)
        assert restored.strip()=="20"
        print("PASS pg_dump y restauracion en base independiente con 20 DEMO")
        print("PASS HTTP salud, JWT local, cuatro consultas, JPEG, modelo ausente, catalogos y tarifas")
        print("PASS seed idempotente, concurrencia, cobro, saldo, alerta, sentido, revision y detecciones")
    finally:
        subprocess.run([pg/"pg_ctl","-D",data,"-m","fast","-w","stop"],check=True)


