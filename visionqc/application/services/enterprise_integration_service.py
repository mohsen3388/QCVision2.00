from __future__ import annotations
from dataclasses import asdict
from typing import Any

class EnterpriseIntegrationService:
    def __init__(self,registry,api_keys,audit,event_bus=None,factory_memory_service=None):
        self.registry=registry; self.api_keys=api_keys; self.audit=audit; self.event_bus=event_bus; self.factory_memory_service=factory_memory_service
    def connector_health(self):
        result=self.registry.health(); self.audit.append("integration.health_checked",entity_type="integration",outcome="Success",details={"connectors":len(result)})
        return result
    def health_payload(self): return {"status":"ok","connectors":[asdict(h) for h in self.registry.health()]}
    def issue_api_key(self,name:str,role:str):
        key_id,secret=self.api_keys.issue(name,role); self.audit.append("integration.api_key_issued",entity_type="api_key",entity_id=key_id,details={"name":name,"role":role}); return key_id,secret
    def disable_api_key(self,key_id:str): self.api_keys.disable(key_id); self.audit.append("integration.api_key_disabled",entity_type="api_key",entity_id=key_id)
    def list_api_keys(self): return self.api_keys.list_all()
    def recent_factory_memory(self,limit:int=25):
        if self.factory_memory_service is None:return []
        cases=self.factory_memory_service.list_recent(limit)
        return [{"case_uuid":c.case_uuid,"status":getattr(c.status,"value",str(c.status)),"product":c.product_name,"line":c.production.production_line,"created_at":c.created_at} for c in cases]
    def deliver_webhook(self,event_type:str,payload:dict[str,Any]):
        connector=self.registry.get("webhook")
        try: status=connector.deliver(event_type,payload); outcome="Success"
        except Exception as exc: status=0; outcome="Failed"; self.audit.append("integration.webhook_delivery",entity_type="webhook",outcome=outcome,details={"event_type":event_type,"error":str(exc)}); raise
        self.audit.append("integration.webhook_delivery",entity_type="webhook",outcome=outcome,details={"event_type":event_type,"http_status":status}); return status
