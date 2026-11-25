"""Exercise real HTTP, SSE and evidence storage with a labeled DEMO inference fixture."""
import concurrent.futures
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import threading
import time

import httpx
from PIL import Image
import uvicorn


def check(app,headers,base):
    import api.main as backend
    class Fixture(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path=="/predict" and self.headers["X-Inference-Key"]=="fixture-local"
            self.rfile.read(int(self.headers["content-length"]))
            data=json.dumps({"plate":"8003TST","vehicle_category":"auto","axles":2,"review_required":True}).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def log_message(self,*args):pass

    fixture=ThreadingHTTPServer(("127.0.0.1",0),Fixture)
    worker=threading.Thread(target=fixture.serve_forever,daemon=True)
    worker.start()
    os.environ["INFERENCE_URL"]=f"http://127.0.0.1:{fixture.server_port}"
    os.environ["INFERENCE_API_KEY"]="fixture-local"
    backend.evidence=Path(base)/"evidencias"
    sock=socket.socket()
    sock.bind(("127.0.0.1",0))
    url=f"http://127.0.0.1:{sock.getsockname()[1]}/api/v1"
    server=uvicorn.Server(uvicorn.Config(app,log_level="error"))
    thread=threading.Thread(target=server.run,kwargs={"sockets":[sock]},daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.05)
        ready=threading.Event()
        def listen():
            name=""
            with httpx.stream("GET",url+"/events/stream",headers=headers,timeout=8) as stream:
                stream.raise_for_status()
                for line in stream.iter_lines():
                    if line.startswith("event: "):name=line[7:]
                    if line.startswith("data: "):
                        if name=="revenue.updated":ready.set()
                        if name=="step.created":return json.loads(line[6:])["id"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            heard=pool.submit(listen)
            assert ready.wait(6)
            buf=io.BytesIO()
            Image.new("RGB",(32,24),"#297268").save(buf,format="JPEG")
            resp=httpx.post(url+"/pasos/frame",headers=headers,data={"caseta":1,"sentido":"ENTRADA","sesion":"DEMO_HTTP"},
                files={"file":("DEMO.jpg",buf.getvalue(),"image/jpeg")})
            resp.raise_for_status()
            step=resp.json()
            assert heard.result(timeout=8)==step["id"] and step["estado"]=="REVISION_MANUAL"
            assert httpx.get(url+"/evidencias/"+step["evidencia"],headers=headers).content==buf.getvalue()
        print("PASS red HTTP DEMO: frame, inferencia fixture, PostgreSQL, evidencia y evento SSE del mismo paso")
    finally:
        server.should_exit=True
        thread.join(timeout=8)
        fixture.shutdown()
        fixture.server_close()
        sock.close()
        os.environ.pop("INFERENCE_URL",None)
        os.environ.pop("INFERENCE_API_KEY",None)
