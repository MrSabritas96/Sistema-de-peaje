from pathlib import Path
import os
os.environ['OMP_NUM_THREADS']='4'
os.environ['MKL_NUM_THREADS']='4'
import torch,yaml
from ultralytics import YOLO
torch.set_num_threads(4)
root=Path.cwd()
dataset=root/'m3_centros';cfg=yaml.safe_load((dataset/'data.yaml').read_text());cfg['path']=str(dataset)
file=root/'m3_smoke.yaml';file.write_text(yaml.safe_dump(cfg))
if __name__=='__main__':
 model=YOLO('yolo11n-pose.pt')
 model.train(data=str(file),epochs=12,imgsz=416,batch=4,device='cpu',workers=0,project=str(root/'runs'),name='m3_piloto',exist_ok=True,seed=42,plots=False,verbose=False,amp=False,mosaic=0,cache=False)
