from __future__ import annotations
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from visionqc.application.services.enterprise_integration_service import EnterpriseIntegrationService
from visionqc.infrastructure.persistence.sqlite_api_keys import SqliteApiKeyRepository
from visionqc.infrastructure.persistence.sqlite_audit import SqliteAuditTrailRepository
from visionqc.integration import ConnectorRegistry, FileExchangeConnector, RestApiConnector, VisionQCRestServer
from visionqc.security.rbac import is_allowed

class Bus:
    def publish(self,event): pass


def build_service(tmp_path):
    keys=SqliteApiKeyRepository(); keys.initialize()
    audit=SqliteAuditTrailRepository(); audit.initialize()
    registry=ConnectorRegistry()
    service=EnterpriseIntegrationService(registry,keys,audit,Bus())
    server=VisionQCRestServer(service,keys,host="127.0.0.1",port=0)
    registry.register(RestApiConnector(server)); registry.register(FileExchangeConnector(tmp_path/"exchange"))
    return service,server,keys


def test_rbac_permissions():
    assert is_allowed("Operator","integration.read")
    assert not is_allowed("Operator","integration.execute")
    assert is_allowed("Administrator","anything")


def test_api_key_issue_authenticate_and_disable(tmp_path, monkeypatch):
    service,server,keys=build_service(tmp_path)
    key_id,secret=service.issue_api_key("MES","Supervisor")
    identity=keys.authenticate(secret)
    assert identity and identity["role"]=="Supervisor"
    service.disable_api_key(key_id)
    assert keys.authenticate(secret) is None


def test_connector_health_and_file_exchange(tmp_path):
    service,server,keys=build_service(tmp_path)
    health=service.connector_health()
    assert len(health)==2
    assert any(h.connector_id=="file-exchange" and h.state.value=="Ready" for h in health)
    assert any(h.connector_id=="rest-api" and h.state.value=="Disabled" for h in health)


def test_rest_health_and_secured_connectors(tmp_path):
    service,server,keys=build_service(tmp_path)
    _,secret=service.issue_api_key("MES","Operator")
    server.start()
    try:
        with urlopen(server.address+"/health",timeout=3) as response:
            payload=json.loads(response.read().decode())
        assert payload["status"]=="ok"
        request=Request(server.address+"/connectors",headers={"X-API-Key":secret})
        with urlopen(request,timeout=3) as response:
            secured=json.loads(response.read().decode())
        assert "connectors" in secured
        try:
            urlopen(server.address+"/connectors",timeout=3)
            assert False,"missing API key should fail"
        except HTTPError as exc:
            assert exc.code==403
    finally:
        server.stop()
