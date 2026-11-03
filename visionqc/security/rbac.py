from __future__ import annotations
ROLE_PERMISSIONS={
 "Operator":{"integration.read","quality.read"},
 "QC":{"integration.read","quality.read","quality.approve"},
 "Supervisor":{"integration.read","integration.execute","quality.read","quality.approve"},
 "Maintenance":{"integration.read","integration.execute","quality.read"},
 "Administrator":{"*"},
 "Auditor":{"integration.read","audit.read","quality.read"},
}
def is_allowed(role:str,permission:str)->bool:
    permissions=ROLE_PERMISSIONS.get(role,set()); return "*" in permissions or permission in permissions
