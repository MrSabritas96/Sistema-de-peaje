"""Prepare M2 mask proposals for visual review; reuse local YOLOE weights."""
from pathlib import Path
import json
import cv2
import numpy as np
from ultralytics import YOLOE

names=["motorcycle","car","minibus","truck","bus","van","sedan"]
classes=[0,1,2,3,4,2,1]
model=YOLOE("yoloe-11l-seg.pt")
model.set_classes(names,model.get_text_pe(names))
out=Path("propuestas_m2")
out.mkdir(exist_ok=True)
for file in sorted(Path("propuestas").glob("*.jpg")):
    dest=out/(file.stem+".txt")
    if dest.exists():continue
    im=cv2.imread(str(file))
    result=model.predict(im,imgsz=640,conf=.18,verbose=False)[0]
    labels=[]
    if result.masks is not None:
        for cls,poly in zip(result.boxes.cls.tolist(),result.masks.xyn):
            if len(poly)<3:continue
            pts=np.clip(poly,0,1).flatten()
            labels.append(str(classes[int(cls)])+" "+" ".join(f"{x:.6f}" for x in pts))
    dest.write_text("\n".join(labels),encoding="utf8")
