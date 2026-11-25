"""OCR sobre la caja de placa con trazabilidad de cada lectura."""
import cv2
import re
PLATE=re.compile(r"[0-9]{3,4}[A-Z]{3}")
ALLOWED="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def read_plate(reader,patch):
    if patch.size==0:return []
    gray=cv2.cvtColor(patch,cv2.COLOR_BGR2GRAY)
    readings=[]
    for name,top in (("completa",0),("sin_encabezado",.23)):
        band=gray[int(gray.shape[0]*top):]
        width=max(48,min(420,round(64*band.shape[1]/band.shape[0])))
        scaled=cv2.resize(band,(width,64),interpolation=cv2.INTER_CUBIC)
        result=reader.recognize(scaled,allowlist=ALLOWED,detail=1)
        if result:
            value="".join(r[1] for r in result).upper()
            readings.append({"variante":name,"texto":value,"confianza":min(float(r[2]) for r in result)})
    if not any(PLATE.fullmatch(r["texto"]) for r in readings) and min(gray.shape)>=10:
        band=gray[int(gray.shape[0]*.20):]
        contrast=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(4,4)).apply(band)
        enhanced=cv2.resize(contrast,(max(48,min(420,round(64*band.shape[1]/band.shape[0]))),64),interpolation=cv2.INTER_CUBIC)
        retry=reader.recognize(enhanced,allowlist=ALLOWED,detail=1)
        if retry:
            readings.append({"variante":"contraste_local","texto":"".join(r[1] for r in retry).upper(),"confianza":min(float(r[2]) for r in retry)})
    return sorted(readings,key=lambda r:(bool(PLATE.fullmatch(r["texto"])),r["confianza"]),reverse=True)
class ClassOCR:
    def __init__(self,path):
        import onnxruntime as ort
        self.session=ort.InferenceSession(str(path),providers=["CPUExecutionProvider"])

    def read(self,patch):
        tensor=cv2.resize(patch[:,:,::-1],(128,64))[None]
        scores=self.session.run(["plate"],{"input":tensor})[0][0]
        indices=scores.argmax(axis=1)
        alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_"
        text="".join(alphabet[i] for i in indices).replace("_","")
        return {"variante":"cct_condra","texto":text,"confianza":float(scores.max(axis=1).mean())}
