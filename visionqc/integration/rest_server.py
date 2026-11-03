from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json, threading
from urllib.parse import urlparse
from visionqc.security.rbac import is_allowed

class VisionQCRestServer:
    def __init__(self,service,api_keys,host="127.0.0.1",port=8765):
        self.service=service; self.api_keys=api_keys; self.host=host; self.port=int(port); self._server=None; self._thread=None
    @property
    def is_running(self): return self._server is not None
    @property
    def address(self): return f"http://{self.host}:{self.port}"
    def start(self):
        if self.is_running:return
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def _json(self,status,payload):
                body=json.dumps(payload,ensure_ascii=False,default=str).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
            def _auth(self,permission):
                if self.path=="/health": return {"role":"Operator","name":"anonymous-health"}
                secret=self.headers.get("X-API-Key",""); identity=owner.api_keys.authenticate(secret)
                if not identity or not is_allowed(identity["role"],permission): self._json(403,{"error":"forbidden"}); return None
                return identity
            def do_GET(self):
                path=urlparse(self.path).path
                if path=="/health": self._json(200,owner.service.health_payload()); return
                identity=self._auth("integration.read")
                if not identity:return
                if path=="/connectors": self._json(200,owner.service.health_payload()); return
                if path=="/factory-memory": self._json(200,owner.service.recent_factory_memory()); return
                self._json(404,{"error":"not_found"})
            def log_message(self,fmt,*args): return
        self._server=ThreadingHTTPServer((self.host,self.port),Handler); self.port=self._server.server_address[1]
        self._thread=threading.Thread(target=self._server.serve_forever,daemon=True,name="VisionQC-REST"); self._thread.start()
    def stop(self):
        if self._server: self._server.shutdown(); self._server.server_close(); self._server=None
        if self._thread: self._thread.join(timeout=2); self._thread=None
