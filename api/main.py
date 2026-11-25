import time
from collections import OrderedDict
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
from typing import Literal

import firebase_admin
from firebase_admin import auth
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
import httpx
import jwt
from PIL import Image, ImageDraw, ImageOps
from pydantic import BaseModel

from .domain import db, init, normalize, query, register

app = FastAPI(title="Peaje La Paz",root_path="")
prefix = "/api/v1"
evidence = Path(os.getenv("EVIDENCE_DIR","evidencias"))
secret = os.environ["JWT_SECRET"]
if len(secret)<32:
    raise RuntimeError("Configura JWT_SECRET de al menos 32 caracteres")


@app.on_event("startup")
def setup():
    init()


@app.get(prefix+"/health")
def health():
    with db.connect() as conn:
        query(conn,"SELECT 1")
    return {"api":"ok","postgres":"ok"}


class Login(BaseModel):
    id_token: str


@app.post(prefix+"/auth/google")
def login(payload: Login, response: Response):
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
    try:
        identity=auth.verify_id_token(payload.id_token,check_revoked=True)
    except Exception:
        raise HTTPException(401,"Token de Google inválido")
    email=identity.get("email","").lower()
    if not identity.get("email_verified") or identity.get("firebase",{}).get("sign_in_provider")!="google.com":
        raise HTTPException(403,"Se requiere una cuenta Google verificada")
    with db.connect() as conn:
        role=query(conn,"SELECT rol FROM usuarios WHERE email=:e AND activo",e=email).scalar()
    if not role:
        raise HTTPException(403,"Cuenta fuera de la lista autorizada")
    token=jwt.encode({"sub":email,"exp":datetime.now(timezone.utc)+timedelta(hours=4)},secret,algorithm="HS256")
    response.set_cookie("peaje",token,secure=True,httponly=True,samesite="lax",max_age=14400)
    return {"access_token":token,"rol":role}


def user(request: Request):
    token=request.headers.get("authorization","").removeprefix("Bearer ") or request.cookies.get("peaje","")
    try:
        email=jwt.decode(token,secret,algorithms=["HS256"],options={"require":["exp","sub"]})["sub"]
    except jwt.InvalidTokenError:
        raise HTTPException(401,"Inicia sesión")
    with db.connect() as conn:
        role=query(conn,"SELECT rol FROM usuarios WHERE email=:e AND activo",e=email).scalar()
    if not role:
        raise HTTPException(403,"Usuario deshabilitado")
    return email,role


@app.get(prefix+"/historial")
def history(account=Depends(user)):
    with db.connect() as conn:
        return query(conn,"SELECT p.*, t.monto AS tarifa_referencia FROM pasos p LEFT JOIN tarifas t ON t.categoria=p.categoria AND t.ejes=p.ejes WHERE p.ocultado_en IS NULL ORDER BY p.id DESC LIMIT 100").mappings().all()


@app.get(prefix+"/alertas")
def alerts(account=Depends(user)):
    with db.connect() as conn:
        return query(conn,"SELECT * FROM alertas ORDER BY id DESC LIMIT 100").mappings().all()


@app.get(prefix+"/consulta/{placa}")
def lookup(placa:str,account=Depends(user)):
    plate=normalize(placa)
    with db.connect() as conn:
        vehicle=query(conn,"SELECT * FROM vehiculos WHERE activo AND placa=:p",p=plate).mappings().first()
        last=query(conn,"SELECT * FROM pasos WHERE placa=:p ORDER BY id DESC LIMIT 1",p=plate).mappings().first()
    state=(("REGISTRADA_Y_CON_PASO" if last else "REGISTRADA_SIN_PASO") if vehicle else
           ("IDENTIFICADA_NO_REGISTRADA" if last else "NO_EXISTE"))
    suggestions=[]
    if state=="NO_EXISTE" and len(plate) in (6,7):
        candidates={plate[:i]+sub+plate[i+1:] for i in range(len(plate)) for sub in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"}
        with db.connect() as conn:
            suggestions=query(conn,"""SELECT placa FROM vehiculos WHERE activo AND placa=ANY(:c)
                UNION SELECT placa FROM pasos WHERE placa=ANY(:c) ORDER BY placa LIMIT 5""",c=sorted(candidates)).scalars().all()
    description={"IDENTIFICADA_NO_REGISTRADA":"Detectada por la cámara. Sin alta en el padrón de vehículos.",
                 "NO_EXISTE":"Sin coincidencia exacta.","REGISTRADA_SIN_PASO":"Registrada sin pasos.",
                 "REGISTRADA_Y_CON_PASO":"Registrada con paso."}[state]
    if last:
        description+=f" Último paso: {last['fecha'].astimezone(timezone(timedelta(hours=-4))):%d/%m/%Y %H:%M}, caseta {last['caseta']}, {last['categoria'] or 'categoría pendiente'}. "
        description+=(f"{last['monto']} Bs." if last['monto'] is not None else "Sin cobro confirmado.")
    if suggestions:
        description+=" ¿Quisiste decir "+", ".join(suggestions)+"?"
    return {"estado":state,"respuesta":description,"vehiculo":vehicle,"ultimo_paso":last,"sugerencias":suggestions}


def annotated(raw, result, limit=1200):
    with Image.open(io.BytesIO(raw)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    w,h=image.size
    image.thumbnail((limit,limit))
    sx,sy=image.width/w,image.height/h
    draw=ImageDraw.Draw(image,"RGBA")
    polygon=[(x*sx,y*sy) for x,y in result.get("vehicle_polygon",[])]
    if len(polygon)>=3 and not result.get("instances"):
        draw.polygon(polygon,fill=(36,168,235,50),outline=(36,168,235,255),width=2)
    colors={"auto":(30,105,225),"minibus":(13,150,127),"bus":(189,68,33),"camion":(148,64,200),"moto":(202,126,10),"persona":(193,45,110)}
    for i,item in enumerate(result.get("instances",[])):
        name=item["category"]
        color=colors.get(name,(60,100,120))
        points=[(x*sx,y*sy) for x,y in item["polygon"]]
        if len(points)>=3:
            draw.polygon(points,fill=(*color,255 if name=="persona" else 62),outline=(*color,255),width=2)
        a,b,c,d=item["box"]; a,b,c,d=a*sx,b*sy,c*sx,d*sy
        draw.rectangle((a,b,c,d),outline=(*color,255),width=2)
        label=f"{name} {item['confidence']:.2f}"
        if i==result.get("target_index"):
            label+=" "+result.get("direction","")
        top=max(0,b-15)
        draw.rectangle((a,top,a+draw.textlength(label)+6,top+15),fill=(*color,255))
        draw.text((a+3,top),label,fill="white")
    box=result.get("plate_bbox")
    if box:
        a,b,c,d=box
        draw.rectangle((a*sx,b*sy,c*sx,d*sy),outline="lime",width=3)
        draw.text((a*sx,max(0,b*sy-14)),result.get("plate") or "OCR pendiente",fill="white",stroke_width=2,stroke_fill="black")
    for pt in result.get("axle_keypoints",[]):
        x,y=pt["x"]*image.width,pt["y"]*image.height
        draw.ellipse((x-5,y-5,x+5,y+5),fill="yellow",outline="black",width=2)
    output=io.BytesIO()
    image.save(output,"JPEG",quality=84)
    return output.getvalue()


@app.get(prefix+"/pasos/{step_id}/inferencia")
def inference_detail(step_id:int,account=Depends(user)):
    with db.connect() as conn:
        row=query(conn,"SELECT d.resultado FROM detecciones d JOIN pasos p ON p.id=d.paso AND p.evidencia=d.evidencia WHERE paso=:step ORDER BY d.id DESC LIMIT 1",step=step_id).scalar()
    if row is None:
        raise HTTPException(404)
    return row


@app.get(prefix+"/evidencias/{digest}")
def photo(digest:str,account=Depends(user)):
    path=evidence/(digest+".jpg")
    if not re.fullmatch("[a-f0-9]{64}",digest) or not path.is_file():
        raise HTTPException(404)
    with db.connect() as conn:
        result=query(conn,"SELECT resultado FROM detecciones WHERE evidencia=:d ORDER BY id LIMIT 1",d=digest).scalar()
    if result and any(result.get(k) for k in ("vehicle_polygon","plate_bbox","axle_keypoints")):
        return Response(annotated(path.read_bytes(),result),media_type="image/jpeg")
    return FileResponse(path,media_type="image/jpeg")


async def analyze(file:UploadFile, plate_only=False):
    raw=await file.read(10*1024*1024+1)
    if len(raw)>10*1024*1024:
        raise HTTPException(413)
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in (("JPEG","PNG","WEBP") if plate_only else ("JPEG",)) or im.width*im.height>20_000_000:
                raise ValueError()
            im.load()
            if im.format!="JPEG":
                buf=io.BytesIO(); ImageOps.exif_transpose(im).convert("RGB").save(buf,"JPEG",quality=92); raw=buf.getvalue()
    except Exception:
        raise HTTPException(422,"Se requiere una imagen JPEG válida")
    url=os.getenv("INFERENCE_URL","")
    if not url or not os.getenv("INFERENCE_API_KEY"):
        raise HTTPException(503,"MODEL_NOT_READY")
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            remote=await client.post(url.rstrip("/")+"/predict",params={"plate_only":"true"} if plate_only else {},files={"file":("frame.jpg",raw,"image/jpeg")},
                                     headers={"X-Inference-Key":os.environ["INFERENCE_API_KEY"]})
            remote.raise_for_status()
            result=remote.json()
        except (httpx.HTTPError,ValueError):
            raise HTTPException(503,"Inferencia no disponible")
    return raw,result


motion_tracks=OrderedDict()

def motion_direction(stream,result):
    box=result.get("target_box")
    now=time.monotonic()
    prior=motion_tracks.pop(stream,None)
    if not box:
        return None
    x=(box[0]+box[2])/2
    y=(box[1]+box[3])/2
    plate=result.get("plate") or ""
    anchor=x
    direction=None
    if prior:
        timestamp,old_x,old_y,old_plate,start,known=prior
        compatible=not (plate and old_plate) or (len(plate)==len(old_plate) and sum(a!=b for a,b in zip(plate,old_plate))<=1)
        if now-timestamp<6 and compatible and abs(y-old_y)<0.15 and abs(x-old_x)<0.35:
            anchor=start
            direction=known
            if abs(x-anchor)>0.045:
                direction="SALIDA" if x>anchor else "ENTRADA"
            plate=plate or old_plate
    motion_tracks[stream]=(now,x,y,plate,anchor,direction)
    if len(motion_tracks)>512:
        motion_tracks.popitem(last=False)
    return direction


@app.post(prefix+"/pasos/frame")
async def frame(file:UploadFile=File(),caseta:int=Form(),sentido:Literal["ENTRADA","SALIDA","AUTO"]=Form(),
                preview:bool=Form(False),sesion:str=Form(min_length=1,max_length=128),account=Depends(user)):
    raw,result=await analyze(file)
    digest=hashlib.sha256(raw).hexdigest()
    evidence.mkdir(parents=True,exist_ok=True)
    if sentido=="AUTO":
        sentido=motion_direction((account[0],caseta,sesion),result)
    result["direction"]=sentido or "Siguiendo"
    with Image.open(io.BytesIO(raw)) as source:
        width,height=ImageOps.exif_transpose(source).size
    overlay={"width":width,"height":height,"objects":[{"box":item["box"],"label":item["category"],"score":item["confidence"]} for item in result.get("instances",[])]}
    preview_image=base64.b64encode(annotated(raw,result,480)).decode() if preview else None
    if not sentido:
        return {"estado":"Esperando movimiento lateral","preview":preview_image,"overlay":overlay}
    if not any(result.get(k) for k in ("vehicle_category","vehicle_polygon","plate_bbox","axle_keypoints")):
        return {"estado":"Buscando vehículo","preview":preview_image,"overlay":overlay}
    with Image.open(io.BytesIO(raw)) as image:
        grey=ImageOps.exif_transpose(image).convert("L").resize((9,8),Image.Resampling.LANCZOS)
        result["visual_hash"]="".join("1" if grey.getpixel((x,y))>grey.getpixel((x+1,y)) else "0" for y in range(8) for x in range(8))
        polygon=result.get("vehicle_polygon")
        if polygon:
            xs,ys=zip(*polygon)
            target=ImageOps.exif_transpose(image).crop((min(xs),min(ys),max(xs)+1,max(ys)+1)).convert("L").resize((9,8),Image.Resampling.LANCZOS)
            result["vehicle_hash"]="".join("1" if target.getpixel((x,y))>target.getpixel((x+1,y)) else "0" for y in range(8) for x in range(8))
    try:
        return dict(register(result,caseta,sentido,account[0],sesion,digest,lambda:(evidence/(digest+".jpg")).write_bytes(raw)),preview=preview_image,overlay=overlay)
    except ValueError as exc:
        raise HTTPException(422,str(exc))


@app.get(prefix+"/events/stream")
async def events(request:Request,account=Depends(user)):
    async def stream():
        previous={}
        seen_alerts=set()
        first=True
        last_beat=0.0
        def event(name,data):
            return "event: "+name+"\ndata: "+json.dumps(jsonable_encoder(data))+"\n\n"
        while not await request.is_disconnected():
            user(request)
            current=history(account)
            marker={row["id"]:dict(row) for row in current}
            if first or marker!=previous:
                yield event("step.snapshot",current)
                for row in reversed(current):
                    if not first and previous.get(row["id"])!=marker[row["id"]]:
                        yield event("step.updated" if row["id"] in previous else "step.created",row)
                with db.connect() as conn:
                    total=query(conn,"SELECT COALESCE(sum(monto),0) FROM pasos WHERE estado='PAGADO'").scalar()
                yield event("revenue.updated",{"total_bob":total})
                previous=marker
            recent=alerts(account)
            ids={a["id"] for a in recent}
            if first or ids!=seen_alerts:
                yield event("alert.snapshot",recent)
                for alert in reversed(recent):
                    if not first and alert["id"] not in seen_alerts:
                        yield event("alert.created",alert)
                seen_alerts=ids
            now=asyncio.get_running_loop().time()
            if now-last_beat>=20:
                yield ": heartbeat\n\n"
                last_beat=now
            first=False
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no"})
from decimal import Decimal
from pydantic import Field


def admin(account=Depends(user)):
    if account[1]!="ADMIN":
        raise HTTPException(403,"Se requiere ADMIN")
    return account


class Vehicle(BaseModel):
    placa:str=Field(pattern=r"^[0-9]{3,4}[A-Z]{3}$")
    categoria:Literal["moto","auto","minibus","camion","bus"]
    saldo:Decimal=Field(ge=0,max_digits=12,decimal_places=2)


class Rate(BaseModel):
    categoria:Literal["moto","auto","minibus","camion","bus"]
    ejes:int=Field(ge=2,le=8)
    monto:Decimal=Field(ge=0,max_digits=12,decimal_places=2)


class Station(BaseModel):
    id:int=Field(ge=1)
    nombre:str=Field(min_length=1,max_length=120)
    origen:str=Field(min_length=1,max_length=120)
    destino:str=Field(min_length=1,max_length=120)


class Member(BaseModel):
    email:str=Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",max_length=255)
    rol:Literal["ADMIN","OPERADOR"]
    activo:bool


@app.put(prefix+"/vehiculos",dependencies=[Depends(admin)])
def save_vehicle(v:Vehicle):
    with db.begin() as conn:
        query(conn,"""INSERT INTO vehiculos(placa,categoria,saldo) VALUES(:placa,:categoria,:saldo)
            ON CONFLICT(placa) DO UPDATE SET categoria=excluded.categoria,saldo=excluded.saldo,activo=true""",**v.model_dump())
    return v


@app.put(prefix+"/tarifas",dependencies=[Depends(admin)])
def save_rate(v:Rate):
    with db.begin() as conn:
        query(conn,"""INSERT INTO tarifas VALUES(:categoria,:ejes,:monto)
            ON CONFLICT(categoria,ejes) DO UPDATE SET monto=excluded.monto""",**v.model_dump())
    return v


@app.put(prefix+"/casetas",dependencies=[Depends(admin)])
def save_station(v:Station):
    with db.begin() as conn:
        query(conn,"""INSERT INTO casetas VALUES(:id,:nombre,:origen,:destino)
            ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre,origen=excluded.origen,destino=excluded.destino,activa=true""",**v.model_dump())
    return v


@app.put(prefix+"/usuarios")
def save_member(v:Member,account=Depends(admin)):
    email=v.email.lower()
    if email==account[0] and (not v.activo or v.rol!="ADMIN"):
        raise HTTPException(409,"Conserva acceso a tu cuenta de administrador")
    with db.begin() as conn:
        query(conn,"""INSERT INTO usuarios VALUES(:email,:rol,:activo)
            ON CONFLICT(email) DO UPDATE SET rol=excluded.rol,activo=excluded.activo""",email=email,rol=v.rol,activo=v.activo)
    return v


@app.get(prefix+"/admin/{resource}",dependencies=[Depends(admin)])
def catalog(resource:Literal["vehiculos","tarifas","casetas","usuarios","observados"]):
    with db.connect() as conn:
        if resource=="observados":
            return query(conn,"""SELECT DISTINCT ON (p.placa) p.placa,p.categoria,p.ejes,p.fecha,p.estado
                FROM pasos p WHERE NULLIF(p.placa,'') IS NOT NULL AND p.ocultado_en IS NULL
                ORDER BY p.placa,p.fecha DESC LIMIT 500""").mappings().all()
        if resource=="vehiculos":
            return query(conn,"SELECT placa,categoria,ejes,saldo,propietario FROM vehiculos WHERE activo AND NOT is_demo ORDER BY placa LIMIT 500").mappings().all()
        return query(conn,f"SELECT * FROM {resource} ORDER BY 1 LIMIT 500").mappings().all()


@app.post(prefix+"/alertas/{alert_id}/atender")
def acknowledge(alert_id:int,account=Depends(user)):
    with db.begin() as conn:
        if not query(conn,"UPDATE alertas SET atendida=true WHERE id=:id RETURNING id",id=alert_id).first():
            raise HTTPException(404)
    return {"atendida":True}


class Question(BaseModel):
    pregunta:str=Field(min_length=1,max_length=1500)


@app.post(prefix+"/chat")
async def chat(q:Question,account=Depends(user)):
    match=re.search(r"(?<![A-Z0-9])([0-9]{3,4}[ -]*[A-Z]{3})(?![A-Z0-9])",q.pregunta.upper())
    if match:
        result=lookup(match.group(1),account)
        return {"respuesta":normalize(match.group(1))+" · "+result["respuesta"],"datos":result}
    # Handle character substitutions only in the digit/letter positions of a plate.
    for match in re.finditer(r"(?<![A-Z0-9])([0-9OIBS]{3,4}[ -]*[A-Z0185]{3})(?![A-Z0-9])",q.pregunta.upper()):
        candidate=normalize(match.group(1))
        corrected=candidate[:-3].translate(str.maketrans("OIBS","0185"))+candidate[-3:].translate(str.maketrans("0185","OIBS"))
        if candidate!=corrected:
            data=lookup(corrected,account)
            if data["estado"]!="NO_EXISTE":
                return {"respuesta":"¿Quisiste decir "+corrected+"? "+data["respuesta"],"datos":data,"sugerencias":[corrected]}
    from .consultas import resumen
    return resumen(q.pregunta) or {"respuesta":"Puedo consultar una placa por texto o foto, contar los vehículos inscritos o las placas detectadas, y revisar los pasos o el total cobrado hoy o ayer. ¿Qué dato del peaje necesitas?"}


@app.post(prefix+"/chat/imagen")
async def image_question(file:UploadFile=File(),account=Depends(user)):
    _,result=await analyze(file,plate_only=True)
    plate=normalize(result.get("plate"))
    if not plate and (result.get("ocr_confidence") or 0)>=0.6:
        raw=normalize(result.get("plate_raw"))
        if re.fullmatch(r"[0-9OIBS]{3,4}[A-Z0185]{3}",raw):
            suggestion=await chat(Question(pregunta=raw),account)
            if suggestion.get("sugerencias"):
                return suggestion
    if not re.fullmatch(r"[0-9]{3,4}[A-Z]{3}",plate):
        return {"respuesta":"No se pudo leer una placa completa. Prueba una foto más cercana."}
    return await chat(Question(pregunta="Consultar la placa "+plate),account)
class Correction(BaseModel):
    placa:str=Field(pattern=r"^[0-9]{3,4}[A-Z]{3}$")
    categoria:Literal["moto","auto","minibus","camion","bus"]
    ejes:int=Field(ge=2,le=8)
    motivo:str=Field(min_length=4,max_length=500)


@app.post(prefix+"/pasos/{step_id}/confirmar")
def confirm(step_id:int,v:Correction,account=Depends(user)):
    with db.begin() as conn:
        step=query(conn,"SELECT * FROM pasos WHERE id=:id FOR UPDATE",id=step_id).mappings().first()
        if not step:
            raise HTTPException(404)
        if step["estado"] not in ("REVISION_MANUAL","SIN_PLACA","ERROR_OCR"):
            raise HTTPException(409,"El paso ya tiene una decisión")
        key=json.dumps([step["caseta"],step["sentido"],v.placa])
        lock=int.from_bytes(hashlib.sha256(key.encode()).digest()[:8],"big",signed=True)
        query(conn,"SELECT pg_advisory_xact_lock(:lock)",lock=lock)
        nearby=query(conn,"""SELECT id FROM pasos WHERE id<>:id AND caseta=:c AND sentido=:s AND placa=:p
            AND estado='PAGADO' AND fecha BETWEEN CAST(:f AS timestamptz)-interval '45 seconds'
            AND CAST(:f AS timestamptz)+interval '45 seconds' LIMIT 1""",id=step_id,c=step["caseta"],s=step["sentido"],p=v.placa,f=step["fecha"]).scalar()
        if nearby:
            raise HTTPException(409,"Existe otro paso cobrado para esta placa dentro de la ventana")
        before=query(conn,"SELECT saldo FROM vehiculos WHERE activo AND placa=:p FOR UPDATE",p=v.placa).scalar()
        amount=query(conn,"SELECT monto FROM tarifas WHERE categoria=:c AND ejes=:e",c=v.categoria,e=v.ejes).scalar()
        after=before
        if before is None:
            state="IDENTIFICADA_NO_REGISTRADA"
        elif amount is None:
            state="TARIFA_NO_CONFIGURADA"
        elif before<amount:
            state="SIN_SALDO"
        else:
            state="PAGADO"
            after=before-amount
            query(conn,"UPDATE vehiculos SET saldo=:saldo WHERE placa=:p",saldo=after,p=v.placa)
        updated=query(conn,"""UPDATE pasos SET placa=:p,categoria=:c,ejes=:e,estado=:s,saldo_anterior=:a,
                saldo_posterior=:b,monto=:m WHERE id=:id RETURNING *""",p=v.placa,c=v.categoria,e=v.ejes,
                s=state,a=before,b=after,m=amount,id=step_id).mappings().one()
        query(conn,"UPDATE alertas SET atendida=true WHERE paso=:id",id=step_id)
        if state!="PAGADO":
            query(conn,"INSERT INTO alertas(paso,tipo) VALUES(:id,:s)",id=step_id,s=state)
        query(conn,"""INSERT INTO auditoria(usuario,entidad,entidad_id,antes,despues,motivo)
            VALUES(:u,'pasos',:id,CAST(:a AS jsonb),CAST(:b AS jsonb),:m)""",u=account[0],id=step_id,
            a=json.dumps(jsonable_encoder(step)),b=json.dumps(jsonable_encoder(updated)),m=v.motivo)
        return updated

@app.delete(prefix+"/admin/{resource}/{identifier}")
def deactivate(resource:Literal["vehiculos","casetas","usuarios","tarifas"],identifier:str,account=Depends(admin)):
    with db.begin() as conn:
        if resource=="vehiculos":
            row=query(conn,"UPDATE vehiculos SET activo=false WHERE placa=:id RETURNING placa",id=normalize(identifier))
        elif resource=="casetas":
            if not identifier.isdecimal():raise HTTPException(422)
            row=query(conn,"UPDATE casetas SET activa=false WHERE id=:id RETURNING id",id=int(identifier))
        elif resource=="usuarios":
            if identifier.lower()==account[0]:raise HTTPException(409,"Conserva tu acceso")
            row=query(conn,"UPDATE usuarios SET activo=false WHERE email=:id RETURNING email",id=identifier.lower())
        else:
            cat,_,num=identifier.partition(",")
            if not num.isdecimal():raise HTTPException(422)
            row=query(conn,"DELETE FROM tarifas WHERE categoria=:cat AND ejes=:num RETURNING categoria",cat=cat,num=int(num))
        if row.first() is None:raise HTTPException(404)
    return {"ok":True}
@app.get(prefix+"/admin-backups",dependencies=[Depends(admin)])
def backups():
    root=Path(os.getenv("BACKUP_DIR","/backups"))
    return sorted(f.name for f in root.glob("*") if f.is_file() and re.fullmatch(r"\d{8}T\d{6}Z(?:\.dump|-evidencias\.tar\.gz)",f.name))


@app.get(prefix+"/admin-backups/{name}",dependencies=[Depends(admin)])
def download_backup(name:str):
    if name not in backups():
        raise HTTPException(404)
    path=Path(os.getenv("BACKUP_DIR","/backups"))/name
    return FileResponse(path,filename=name,media_type="application/octet-stream")
class PlateQuestion(BaseModel):
    placa:str=Field(min_length=1,max_length=24)


@app.post(prefix+"/placas/consultar")
def plate_question(q:PlateQuestion,account=Depends(user)):
    return lookup(q.placa,account)


@app.get(prefix+"/placas/{placa}/historial")
def plate_history(placa:str,account=Depends(user)):
    with db.connect() as conn:
        return query(conn,"SELECT p.*, t.monto AS tarifa_referencia FROM pasos p LEFT JOIN tarifas t ON t.categoria=p.categoria AND t.ejes=p.ejes WHERE placa=:p AND p.ocultado_en IS NULL ORDER BY fecha DESC",p=normalize(placa)).mappings().all()


@app.get(prefix+"/casetas/{id}/resumen")
def booth_summary(id:int,account=Depends(user)):
    with db.connect() as conn:
        if not query(conn,"SELECT 1 FROM casetas WHERE id=:id",id=id).first():
            raise HTTPException(404,"Caseta inexistente")
        return query(conn,"""SELECT count(*) AS pasos, COALESCE(sum(monto) FILTER (WHERE estado='PAGADO'),0) AS recaudacion_bob
            FROM pasos WHERE caseta=:id AND (fecha AT TIME ZONE 'America/La_Paz')::date =
            (now() AT TIME ZONE 'America/La_Paz')::date""",id=id).mappings().one()


@app.post(prefix+"/placas/consultar-imagen")
async def lookup_image(file:UploadFile=File(),account=Depends(user)):
    _,result=await analyze(file,plate_only=True)
    plate=normalize(result.get("plate"))
    if not re.fullmatch(r"[0-9]{3,4}[A-Z]{3}",plate):
        raise HTTPException(422,"No se pudo leer la placa. Prueba con otra imagen.")
    return lookup(plate,account)


app.add_api_route(prefix+"/agente/chat",chat,methods=["POST"])

@app.get(prefix+"/monitor")
def monitor(account=Depends(user)):
    with db.connect() as conn:
        database=dict(query(conn,"SELECT current_database() AS base,count(*) AS pasos,clock_timestamp() AS hora FROM pasos").mappings().one())
    try:
        try:
            app_instance=firebase_admin.get_app()
        except ValueError:
            app_instance=firebase_admin.initialize_app()
        identity=auth.get_user_by_email(account[0],app=app_instance)
        identity_result={"proyecto":app_instance.project_id,"proveedores":[p.provider_id for p in identity.provider_data]}
    except Exception:
        identity_result={"estado":"Consulta de identidad no disponible"}
    try:
        response=httpx.get(os.environ["INFERENCE_URL"].rstrip("/")+"/health",headers={"X-Inference-Key":os.environ["INFERENCE_API_KEY"]},timeout=5)
        response.raise_for_status()
        inference={"modelos_listos":response.json()["model_ready"],"respuesta_ms":round(response.elapsed.total_seconds()*1000)}
    except (ValueError,KeyError,httpx.HTTPError):
        inference={"estado":"Servicio sin respuesta"}
    return {"PostgreSQL":database,"Firebase Authentication":identity_result,"Servicio de inferencia":inference}

@app.get(prefix+"/sesion")
def session_role(account=Depends(user)):
    return {"rol":account[1]}


@app.post(prefix+"/pasos/{step_id}/ocultar")
def hide_step(step_id:int,account=Depends(admin)):
    with db.begin() as conn:
        found=query(conn,"""UPDATE pasos SET ocultado_por=coalesce(ocultado_por,:email),
            ocultado_en=coalesce(ocultado_en,clock_timestamp()) WHERE id=:id RETURNING id""",
            email=account[0],id=step_id).scalar()
        if found is None:
            raise HTTPException(404,"Paso inexistente")
    return {"id":found}
