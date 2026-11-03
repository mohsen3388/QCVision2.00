from __future__ import annotations
from .models import Session
from .repository import SecurityRepository

class SecurityGovernanceService:
    def __init__(self, repository: SecurityRepository, audit_repository) -> None:
        self.repository=repository; self.audit=audit_repository
        self.repository.initialize(); self._session=Session("admin","System Administrator","Administrator")

    @property
    def session(self) -> Session: return self._session

    def login(self, username: str, password: str) -> bool:
        user=self.repository.authenticate(username,password)
        ok=user is not None
        self.audit.append("security.login",username or "anonymous",outcome="Success" if ok else "Denied")
        if user: self._session=Session(user.username,user.display_name,user.role)
        return ok

    def create_user(self, username, display_name, role, password, must_change=True):
        self.require("*"); self.repository.upsert_user(username,display_name,role,password,must_change)
        self.audit.append("security.user.saved",self.session.username,"user",username,details={"role":role})

    def require(self, permission: str):
        if not self.session.can(permission): raise PermissionError(f"Permission denied: {permission}")

    def lock_template(self,key:str,locked:bool,reason:str=""):
        self.require("quality.configure"); self.repository.set_lock("template",key,locked,self.session.username,reason)
        self.audit.append("governance.template.lock",self.session.username,"template",key,details={"locked":locked,"reason":reason})
