"""Export foreground vehicle crops and wheel proposals. Run from datos_locales."""
from pathlib import Path
import json
import zipfile
import cv2
import numpy as np
import torch
from ultralytics import YOLO,YOLOE

source=Path(__file__).resolve().parent/"keypoints_llantas_yolo_detectron2_v3.ipynb"
cells=json.loads(source.read_text(encoding="utf8"))["cells"]
config="".join(cells[4]["source"])
exec(config[config.index("DEVICE ="):])
exec("".join(cells[8]["source"]))
exec("".join(cells[11]["source"]))
root=Path("propuestas")
root.mkdir(exist_ok=True)
with zipfile.ZipFile("LaPaz_279_unicas.zip") as archive:
    for name in sorted(archive.namelist()):
        stem=Path(name).stem
        dest=root/(stem+".json")
        if dest.exists():
            continue
        frame=cv2.imdecode(np.frombuffer(archive.read(name),np.uint8),cv2.IMREAD_COLOR)
        vehicles,_=analizar_yoloe(frame,0.35)
        proposals=[]
        box=None
        if vehicles:
            largest=max(vehicles,key=lambda v:(v["box"][2]-v["box"][0])*(v["box"][3]-v["box"][1]))
            box=[int(max(0,n)) for n in largest["box"]]
            l,t,r,b=box
            crop=frame[t:b,l:r]
            CONF_LLANTA=0.04
            _,wheels=kp_zeroshot(crop,0.35)
            CONF_LLANTA=0.15
            proposals=[{"box":w["box"],"kps":w["kps"].tolist(),"conf":w["conf"]} for w in wheels]
            cv2.imwrite(str(root/(stem+".jpg")),crop)
        temp=dest.with_suffix(".tmp")
        temp.write_text(json.dumps({"source":name,"crop":box,"reviewed":False,"wheels":proposals}))
        temp.replace(dest)
