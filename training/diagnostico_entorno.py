from importlib import metadata
import platform

print("Python",platform.python_version(),platform.platform())
for name in ["torch","ultralytics","easyocr","fastapi","SQLAlchemy","psycopg","firebase-admin"]:
    try: print(name,metadata.version(name))
    except metadata.PackageNotFoundError: print(name,"sin instalar")
try:
    import torch
    print("CUDA",torch.version.cuda,"disponible",torch.cuda.is_available())
    if torch.cuda.is_available():print("GPU",torch.cuda.get_device_name(0))
except ImportError: pass
