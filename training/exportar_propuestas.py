"""Build a wheel annotation import and a separate eight-center M3 pilot."""
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image

root=Path(__file__).resolve().parents[1]
local=root/"datos_locales"
proposals=local/"propuestas"
approved=json.loads((root/"datasets/ruedas_revisadas.json").read_text())
def line(numbers):
    return " ".join(f"{v:.6f}" for v in numbers)
def frame(box,xmax,ymax):
    l,t,r,b=box
    return [(l+r)/(2*xmax),(t+b)/(2*ymax),(r-l)/xmax,(b-t)/ymax]
with ZipFile(local/"Llantas_para_revisar.zip","w",ZIP_DEFLATED) as wheels,ZipFile(local/"M3_piloto_revisado.zip","w",ZIP_DEFLATED) as pose:
    wheels.writestr("data.yaml","train: images/train\nnames: [llanta]\nkpt_shape: [5, 3]\nflip_idx: [0,1,2,4,3]\n")
    pose.writestr("data.yaml","train: images/train\nnames: [vehiculo]\nkpt_shape: [8, 3]\nflip_idx: [0,1,2,3,4,5,6,7]\n")
    for file in sorted(proposals.glob("*.json")):
        rec=json.loads(file.read_text())
        if not rec["crop"]:
            continue
        stem=file.stem
        jpg=file.with_suffix(".jpg")
        with Image.open(jpg) as im: w,h=im.size
        manual=approved.get(stem)
        labels=[]
        points=manual["wheels"] if manual else [row["kps"] for row in rec["wheels"]]
        for i,group in enumerate(points):
            coords=[(max(0,min(w-1,p[0])),max(0,min(h-1,p[1]))) for p in group]
            x,y=zip(*coords)
            box=[min(x),min(y),max(x),max(y)]
            if box[2]<=box[0] or box[3]<=box[1]:continue
            vals=frame(box,w,h)
            for j,(px,py) in enumerate(coords):
                visible=1 if manual and [i,j] in manual.get("occluded",[]) else 2
                vals.extend([px/w,py/h,visible])
            labels.append("0 "+line(vals))
        wheels.write(jpg,"images/train/"+jpg.name)
        wheels.writestr("labels/train/"+stem+".txt","\n".join(labels))
        if manual:
            vals=[0.5,0.5,1,1]
            for group in points:vals.extend([group[0][0]/w,group[0][1]/h,2])
            vals.extend([0,0,0]*(8-len(points)))
            pose.write(jpg,"images/train/"+jpg.name)
            pose.writestr("labels/train/"+stem+".txt","0 "+line(vals))
    wheels.writestr("LEEME.txt","Propuestas de YOLOE sobre recortes del vehiculo principal. Solo los cuatro ejemplos de ruedas_revisadas.json fueron corregidos manualmente. Una etiqueta vacia indica revision pendiente. Antes de entrenar, corregir etiquetas y dividir por secuencia.")
    pose.writestr("LEEME.txt","Cuatro recortes revisados para comprobar el formato. No constituyen un conjunto de entrenamiento o prueba representativo.")
