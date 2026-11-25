FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir ultralytics==8.3.161 easyocr==1.7.2 onnxruntime==1.20.1 fastapi==0.115.12 uvicorn==0.34.2 python-multipart==0.0.20
COPY inference /srv/inference
CMD ["uvicorn","inference.main:app","--host","0.0.0.0","--port","8000"]
