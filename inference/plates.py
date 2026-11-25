"""YOLOv9-t ONNX del proyecto placas-web, con una sesión persistente."""
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort


class PlateDetector:
    def __init__(self,path:Path):
        options=ort.SessionOptions()
        options.intra_op_num_threads=2
        self.session=ort.InferenceSession(str(path),options,providers=["CPUExecutionProvider"])
        self.input=self.session.get_inputs()[0].name

    def boxes(self,image,threshold=0.4):
        h,w=image.shape[:2]
        scale=min(384/h,384/w)
        width,height=max(1,round(w*scale)),max(1,round(h*scale))
        left,top=(384-width)//2,(384-height)//2
        canvas=np.full((384,384,3),114,dtype=np.uint8)
        canvas[top:top+height,left:left+width]=cv2.resize(image,(width,height))
        tensor=(canvas[:,:,::-1].transpose(2,0,1).astype(np.float32)/255)[None]
        detections=self.session.run(None,{self.input:tensor})[0]
        boxes=[]
        for _,x1,y1,x2,y2,_,score in detections:
            if score<threshold:continue
            a,b=max(0,int((x1-left)/scale)),max(0,int((y1-top)/scale))
            c,d=min(w,int((x2-left)/scale)),min(h,int((y2-top)/scale))
            if c>a and d>b:boxes.append((a,b,c,d))
        return boxes
