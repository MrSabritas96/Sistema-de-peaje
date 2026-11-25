from pathlib import Path
import os
os.environ['OMP_NUM_THREADS']='4'
os.environ['MKL_NUM_THREADS']='4'
import torch,yaml
from ultralytics import YOLO
torch.set_num_threads(4)
root=Path.cwd()
dataset=root/'m2_revisado';cfg=yaml.safe_load((dataset/'data.yaml').read_text());cfg['path']=str(dataset)
file=root/'m2_smoke.yaml';file.write_text(yaml.safe_dump(cfg))
if __name__=='__main__':
 model=YOLO('yolo11n-seg.pt')
 model.train(data=str(file),epochs=18,imgsz=416,batch=4,device='cpu',workers=0,project=str(root/'runs'),name='m2_piloto',exist_ok=True,seed=42,plots=False,verbose=False,amp=False,mosaic=0,cache=False)

