import hmac
import io
import os
from pathlib import Path
import re
import time

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
import numpy as np
from PIL import Image, ImageOps

app = FastAPI(title="Inferencia de peaje")
models = {}
reader = None
class_ocr = None
locator = None
visual_encoder = text_vectors = clip_transform = None
started = time.monotonic()
paths = {key:Path(os.getenv("MODEL_DIR","/weights"))/(key+".pt") for key in ("m1","m2","m3")}


@app.on_event("startup")
def load():
    global reader,class_ocr,locator,visual_encoder,text_vectors,clip_transform
    directory=paths["m1"].parent
    if (directory/"vehicle-visual.pt").exists():
        import torch
        from torchvision import transforms as T
        device="cuda" if torch.cuda.is_available() else "cpu"
        visual_encoder=torch.jit.load(str(directory/"vehicle-visual.pt"),map_location=device).eval()
        if device=="cpu":
            visual_encoder=visual_encoder.float()
        text_vectors=torch.load(directory/"vehicle-text.pt",map_location=device,weights_only=True)
        clip_transform=T.Compose([T.Resize(224,T.InterpolationMode.BICUBIC),T.CenterCrop(224),T.ToTensor(),
                                  T.Normalize((.48145466,.4578275,.40821073),(.26862954,.26130258,.27577711))])
    from ultralytics import YOLO
    locator_path=paths["m1"].parent/"general-seg.pt"
    if not locator_path.exists():
        locator_path=paths["m1"].parent/"localizador.pt"
    if locator_path.exists():
        locator=YOLO(str(locator_path))
    for key,path in paths.items():
        if path.is_file():
            model=YOLO(str(path))
            expected={"m1":"detect","m2":"segment","m3":"pose"}[key]
            if model.task!=expected:
                continue
            if key=="m3" and list(model.model.yaml.get("kpt_shape",[])) not in ([8,3],[1,3]):
                continue
            models[key]=model
    recovered=paths["m1"].with_suffix(".onnx")
    if "m1" not in models and recovered.is_file():
        from .plates import PlateDetector
        models["m1"]=PlateDetector(recovered)
    companion=paths["m1"].parent/"ocr-clase.onnx"
    if companion.exists():
        from .ocr import ClassOCR
        class_ocr=ClassOCR(companion)
    if "m1" in models:
        import easyocr
        import torch
        reader=easyocr.Reader(["en"],gpu=torch.cuda.is_available())


def authorize(x_inference_key:str=Header(default="")):
    secret=os.getenv("INFERENCE_API_KEY","")
    if not secret or not hmac.compare_digest(secret,x_inference_key):
        raise HTTPException(401)


@app.get("/health",dependencies=[Depends(authorize)])
def health():
    return {"model_ready":len(models)==3 and reader is not None,
            "missing":[key for key in paths if key not in models],"uptime_s":round(time.monotonic()-started)}


@app.post("/predict",dependencies=[Depends(authorize)])
def predict(file:UploadFile=File(),plate_only:bool=False):
    if not health()["model_ready"]:
        raise HTTPException(503,{"code":"MODEL_NOT_READY","missing":health()["missing"]})
    start=time.monotonic()
    raw=file.file.read(10485761)
    if len(raw)>10485760:
        raise HTTPException(413)
    try:
        with Image.open(io.BytesIO(raw)) as photo:
            if photo.width*photo.height>20000000 or photo.format!="JPEG":
                raise ValueError()
            image=np.asarray(ImageOps.exif_transpose(photo).convert("RGB"))
    except Exception:
        raise HTTPException(422,"JPEG invÃƒÂ¡lido")
    frame=image[:,:,::-1].copy()
    result={"plate":None,"plate_raw":None,"plate_bbox":None,"ocr_confidence":0.0,
            "pasajeros":None,"vehicle_category":None,"category_confidence":0.0,"axles":None,"axle_keypoints":[],"review_required":True}
    if plate_only:
        from .ocr import read_plate
        detector=models["m1"]
        boxes=detector.boxes(frame) if hasattr(detector,"boxes") else detector(frame,verbose=False)[0].boxes.xyxy.int().tolist()
        patches=[frame[t:b,a:c] for a,t,c,b in sorted(boxes,key=lambda q:(q[2]-q[0])*(q[3]-q[1]),reverse=True)[:3]]
        if not patches or 1.3<=frame.shape[1]/frame.shape[0]<=4:
            patches.append(frame)
        for patch in patches:
            readings=[class_ocr.read(patch)] if class_ocr else []
            if not readings or not re.fullmatch(r"[0-9]{3,4}[A-Z]{3}",readings[0]["texto"]):
                readings+=read_plate(reader,patch)
            for reading in readings:
                if reading["confianza"]>=0.6 and re.fullmatch(r"[0-9]{3,4}[A-Z]{3}",reading["texto"]):
                    result.update(plate=reading["texto"],ocr_confidence=reading["confianza"])
                    break
            if result["plate"]:
                break
        result["latency_ms"]=round(1000*(time.monotonic()-start))
        if result["plate"]:
            return result
    origin_x=origin_y=0
    scene=frame
    target_class=None
    if locator is not None:
        located=locator(frame,classes=[0,2,3,5,7],verbose=False)[0]
        names={0:"persona",2:"auto",3:"moto",5:"bus",7:"camion"}
        instances=[]
        for i,(bounds,confidence,cls) in enumerate(zip(located.boxes.xyxy.int().tolist(),located.boxes.conf.tolist(),located.boxes.cls.int().tolist())):
            polygon=located.masks.xy[i] if located.masks is not None else []
            instances.append(dict(category=names[cls],confidence=confidence,box=bounds,
                polygon=[[int(x),int(y)] for x,y in polygon[::max(1,len(polygon)//160)]]))
        result["instances"]=instances
        vehicles=[i for i,item in enumerate(instances) if item["category"]!="persona"]
        if vehicles:
            target=max(vehicles,key=lambda i:(instances[i]["box"][2]-instances[i]["box"][0])*(instances[i]["box"][3]-instances[i]["box"][1]))
            result["target_index"]=target
            result["target_box"]=(located.boxes.xyxyn[target]).tolist()
            origin_x,origin_y,right,bottom=located.boxes.xyxy[target].int().tolist()
            scene=frame[origin_y:bottom,origin_x:right]
            # Estimate visible occupants from person masks contained in the upper cabin.
            width,height=right-origin_x,bottom-origin_y
            if located.masks is not None and width>0 and height>0:
                count=0
                for person in instances:
                    if person["category"]!="persona" or not person["polygon"]:
                        continue
                    left,top,end,base=person["box"]
                    inside=(origin_x<=left<end<=right and origin_y<=top<base<=origin_y+0.72*height)
                    person["ocupante_estimado"]=inside and person["confidence"]>=0.45
                    count+=int(person["ocupante_estimado"])
                result["pasajeros"]=count
            target_class={2:"auto",3:"moto",5:"bus",7:"camion"}[int(located.boxes.cls[target])]
            score=float(located.boxes.conf[target])
            if located.masks is not None:
                result["vehicle_polygon"]=located.masks.xy[target].astype(int).tolist()
    seg=models["m2"](scene,imgsz=416,verbose=False)[0]
    crop=None
    if len(seg.boxes):
        i=int(seg.boxes.xywh[:,2:].prod(1).argmax())
        x,y,r,b=seg.boxes.xyxy[i].int().tolist()
        crop=scene[y:b,x:r]
        x,y=x+origin_x,y+origin_y
        result.update(vehicle_category=seg.names[int(seg.boxes.cls[i])],category_confidence=float(seg.boxes.conf[i]),category_source="m2")
        if "vehicle_polygon" not in result and seg.masks is not None:
            result["vehicle_polygon"]=(seg.masks.xy[i]+[origin_x,origin_y]).astype(int).tolist()
    if target_class is not None:
        crop=scene
        x,y=origin_x,origin_y
        if score>=0.65 and (result["category_confidence"]<0.60 or (target_class=="bus" and score>=0.75)):
            result.update(vehicle_category=target_class,category_confidence=score,category_source="segmentacion_general")
    if target_class is not None and result["vehicle_category"]:
        instances[target].update(category=result["vehicle_category"],confidence=result["category_confidence"])
    if visual_encoder is not None and target_class is not None:
        import torch
        candidates=[j for j in vehicles if instances[j]["category"] in ("camion","auto","minibus") and min(instances[j]["box"][2]-instances[j]["box"][0],instances[j]["box"][3]-instances[j]["box"][1])>=48]
        candidates=sorted(candidates,key=lambda j:j!=target)[:8]
        if candidates:
            pil=Image.fromarray(image)
            batch=torch.stack([clip_transform(pil.crop(instances[j]["box"])) for j in candidates]).to(text_vectors.device)
            with torch.inference_mode():
                features=visual_encoder(batch.half() if batch.is_cuda else batch).float()
                probs=(100*torch.nn.functional.normalize(features)@text_vectors.T).softmax(1)[:,1].tolist()
            for j,prob in zip(candidates,probs):
                if prob>=0.90:
                    instances[j].update(category="minibus",confidence=prob)
                    if j==target:
                        result.update(vehicle_category="minibus",category_confidence=prob,category_source="contraste_visual")
    if crop is not None:
        if crop.size:
            detector=models["m1"]
            if hasattr(detector,"boxes"):
                boxes=detector.boxes(crop)
            else:
                boxes=detector(crop,verbose=False)[0].boxes.xyxy.cpu().numpy().astype(int)
            if len(boxes):
                # Prioritize the largest plate on the selected foreground vehicle.
                a,t,c,d=max(boxes,key=lambda box:(box[2]-box[0])*(box[3]-box[1]))
                result["plate_bbox"]=[int(a+x),int(t+y),int(c+x),int(d+y)]
                patch=crop[max(0,t-2):d+2,max(0,a-2):c+2]
                from .ocr import read_plate
                readings=[]
                if class_ocr is not None and patch.size:
                    candidate=class_ocr.read(patch)
                    if re.fullmatch(r"[0-9]{3,4}[A-Z]{3}",candidate["texto"]):
                        readings.insert(0,candidate)
                if not readings or readings[0]["confianza"]<0.92:
                    readings.extend(read_plate(reader,patch))
                result["ocr_lecturas"]=readings
                if readings:
                    best=readings[0]
                    result.update(plate_raw=best["texto"],plate=best["texto"] if re.fullmatch(r"[0-9]{3,4}[A-Z]{3}",best["texto"]) else None,ocr_confidence=best["confianza"])
            wheel_instances=models["m3"].model.yaml["kpt_shape"][0]==1
            wheel_crop,wx,wy=crop,x,y
            if crop.shape[0]*crop.shape[1]>=0.95*frame.shape[0]*frame.shape[1]:
                wheel_crop,wx,wy=frame,0,0
            pose=models["m3"](wheel_crop,imgsz=640 if wheel_instances else 416,iou=0.25 if wheel_instances else 0.7,verbose=False)[0]
            if pose.keypoints is not None and (wheel_instances or len(pose.boxes)==1):
                for box,points in zip(pose.boxes,pose.keypoints.data.cpu().tolist()):
                    for px,py,confidence in points:
                        if confidence<0.65 or (wheel_instances and float(box.conf[0])<0.35):
                            continue
                        if wheel_instances and py<wheel_crop.shape[0]*0.40:
                            continue
                        result["axle_keypoints"].append({"x":(px+wx)/frame.shape[1],"y":(py+wy)/frame.shape[0],"confidence":confidence})
                count=len(result["axle_keypoints"])
                if 2<=count<=8:
                    result["axles"]=count
    result["latency_ms"]=round(1000*(time.monotonic()-start))
    return result
