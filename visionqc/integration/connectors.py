from __future__ import annotations
import importlib.util, json, socket, time, urllib.request
from pathlib import Path
from typing import Any
from visionqc.domain.enterprise_integration import ConnectorHealth, ConnectorKind, ConnectorState
from .base import BaseConnector

class RestApiConnector(BaseConnector):
    connector_id = "rest-api"; name = "VisionQC REST API"
    def __init__(self, server) -> None: self.server = server
    def health(self) -> ConnectorHealth:
        running = bool(getattr(self.server, "is_running", False))
        return ConnectorHealth(self.connector_id,self.name,ConnectorKind.REST,ConnectorState.READY if running else ConnectorState.DISABLED,"Listening" if running else "REST API server is stopped",metadata={"address": self.server.address})

class MqttConnector(BaseConnector):
    connector_id = "mqtt"; name = "Factory MQTT Broker"
    def __init__(self, config: dict[str,Any]) -> None: self.config=config
    def health(self) -> ConnectorHealth:
        host=str(self.config.get("host","")).strip(); port=int(self.config.get("port",1883) or 1883)
        if not host: return ConnectorHealth(self.connector_id,self.name,ConnectorKind.MQTT,ConnectorState.NOT_CONFIGURED,"Broker host is not configured")
        if importlib.util.find_spec("paho.mqtt.client") is None: return ConnectorHealth(self.connector_id,self.name,ConnectorKind.MQTT,ConnectorState.UNAVAILABLE,"Optional package paho-mqtt is not installed")
        started=time.perf_counter()
        try:
            with socket.create_connection((host,port),timeout=1.5): pass
            return ConnectorHealth(self.connector_id,self.name,ConnectorKind.MQTT,ConnectorState.READY,"Broker TCP endpoint is reachable",(time.perf_counter()-started)*1000,{"host":host,"port":port})
        except OSError as exc: return ConnectorHealth(self.connector_id,self.name,ConnectorKind.MQTT,ConnectorState.DEGRADED,f"Broker unreachable: {exc}",metadata={"host":host,"port":port})

class OpcUaConnector(BaseConnector):
    connector_id = "opcua"; name = "Factory OPC-UA"
    def __init__(self, config: dict[str,Any]) -> None: self.config=config
    def health(self) -> ConnectorHealth:
        endpoint=str(self.config.get("endpoint","")).strip()
        if not endpoint: return ConnectorHealth(self.connector_id,self.name,ConnectorKind.OPC_UA,ConnectorState.NOT_CONFIGURED,"OPC-UA endpoint is not configured")
        if importlib.util.find_spec("opcua") is None and importlib.util.find_spec("asyncua") is None: return ConnectorHealth(self.connector_id,self.name,ConnectorKind.OPC_UA,ConnectorState.UNAVAILABLE,"Optional OPC-UA client package is not installed",metadata={"endpoint":endpoint})
        return ConnectorHealth(self.connector_id,self.name,ConnectorKind.OPC_UA,ConnectorState.DEGRADED,"Client library available; live session has not been commissioned",metadata={"endpoint":endpoint})

class WebhookConnector(BaseConnector):
    connector_id = "webhook"; name = "Outbound Webhook"
    def __init__(self, config: dict[str,Any]) -> None: self.config=config
    def health(self) -> ConnectorHealth:
        url=str(self.config.get("url","")).strip()
        return ConnectorHealth(self.connector_id,self.name,ConnectorKind.WEBHOOK,ConnectorState.READY if url else ConnectorState.NOT_CONFIGURED,"Target configured" if url else "Webhook URL is not configured",metadata={"url":url})
    def deliver(self,event_type:str,payload:dict[str,Any],timeout:float=5.0)->int:
        url=str(self.config.get("url","")).strip()
        if not url: raise RuntimeError("Webhook URL is not configured")
        data=json.dumps({"event_type":event_type,"payload":payload}).encode("utf-8")
        req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=timeout) as response: return int(response.status)

class FileExchangeConnector(BaseConnector):
    connector_id="file-exchange"; name="Secure File Exchange"
    def __init__(self,path:Path)->None: self.path=path
    def health(self)->ConnectorHealth:
        try:
            self.path.mkdir(parents=True,exist_ok=True); probe=self.path/".visionqc_probe"; probe.write_text("ok",encoding="utf-8"); probe.unlink()
            return ConnectorHealth(self.connector_id,self.name,ConnectorKind.FILE,ConnectorState.READY,"Exchange directory is writable",metadata={"path":str(self.path)})
        except OSError as exc: return ConnectorHealth(self.connector_id,self.name,ConnectorKind.FILE,ConnectorState.UNAVAILABLE,str(exc),metadata={"path":str(self.path)})
