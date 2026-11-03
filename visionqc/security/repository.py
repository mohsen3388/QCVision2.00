from __future__ import annotations
import hashlib, hmac, json, os
from datetime import datetime, timezone
from typing import Any
from visionqc.core.database import connect
from .models import UserAccount


def now() -> str: return datetime.now(timezone.utc).isoformat()

def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return salt.hex(), digest.hex()

class SecurityRepository:
    def initialize(self) -> None:
        with connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS security_users(
              username TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL,
              password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1, must_change_password INTEGER NOT NULL DEFAULT 0,
              failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT, last_login_at TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS configuration_locks(
              resource_type TEXT NOT NULL, resource_key TEXT NOT NULL, locked INTEGER NOT NULL DEFAULT 1,
              actor TEXT NOT NULL, reason TEXT, updated_at TEXT NOT NULL,
              PRIMARY KEY(resource_type, resource_key));
            CREATE TABLE IF NOT EXISTS template_version_snapshots(
              id INTEGER PRIMARY KEY AUTOINCREMENT, template_key TEXT NOT NULL, version TEXT NOT NULL,
              lifecycle TEXT NOT NULL, snapshot_json TEXT NOT NULL, checksum TEXT NOT NULL,
              actor TEXT NOT NULL, approval_state TEXT NOT NULL DEFAULT 'Draft', created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_template_versions_key ON template_version_snapshots(template_key,id DESC);
            """)
        self.ensure_default_admin()

    def ensure_default_admin(self) -> None:
        with connect() as c:
            exists = c.execute("SELECT 1 FROM security_users LIMIT 1").fetchone()
        if not exists:
            self.upsert_user("admin", "System Administrator", "Administrator", "VisionQC-Admin-ChangeMe", True)

    def upsert_user(self, username: str, display_name: str, role: str, password: str | None = None, must_change: bool = False) -> None:
        self.initialize_no_seed()
        ts=now()
        with connect() as c:
            row=c.execute("SELECT password_salt,password_hash,created_at FROM security_users WHERE username=?",(username,)).fetchone()
            if password:
                salt,digest=hash_password(password)
            elif row:
                salt,digest=row[0],row[1]
            else:
                raise ValueError("Password is required for a new user")
            created=row[2] if row else ts
            c.execute("""INSERT INTO security_users(username,display_name,role,password_salt,password_hash,active,must_change_password,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(username) DO UPDATE SET display_name=excluded.display_name,role=excluded.role,password_salt=excluded.password_salt,password_hash=excluded.password_hash,active=excluded.active,must_change_password=excluded.must_change_password,updated_at=excluded.updated_at""",
            (username,display_name,role,salt,digest,1,1 if must_change else 0,created,ts))

    def initialize_no_seed(self):
        with connect() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS security_users(username TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL,password_salt TEXT NOT NULL,password_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,must_change_password INTEGER NOT NULL DEFAULT 0,failed_attempts INTEGER NOT NULL DEFAULT 0,locked_until TEXT,last_login_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);""")

    def list_users(self) -> list[UserAccount]:
        self.initialize()
        with connect() as c: rows=c.execute("SELECT username,display_name,role,active,must_change_password,last_login_at FROM security_users ORDER BY username").fetchall()
        return [UserAccount(r[0],r[1],r[2],bool(r[3]),bool(r[4]),r[5]) for r in rows]

    def authenticate(self, username: str, password: str) -> UserAccount | None:
        self.initialize()
        with connect() as c:
            row=c.execute("SELECT username,display_name,role,password_salt,password_hash,active,must_change_password,last_login_at FROM security_users WHERE username=?",(username,)).fetchone()
            if not row or not row[5]: return None
            _,digest=hash_password(password,bytes.fromhex(row[3]))
            if not hmac.compare_digest(digest,row[4]):
                c.execute("UPDATE security_users SET failed_attempts=failed_attempts+1,updated_at=? WHERE username=?",(now(),username)); return None
            ts=now(); c.execute("UPDATE security_users SET failed_attempts=0,last_login_at=?,updated_at=? WHERE username=?",(ts,ts,username))
        return UserAccount(row[0],row[1],row[2],True,bool(row[6]),ts)

    def set_active(self, username: str, active: bool) -> None:
        with connect() as c: c.execute("UPDATE security_users SET active=?,updated_at=? WHERE username=?",(1 if active else 0,now(),username))

    def set_lock(self, resource_type: str, resource_key: str, locked: bool, actor: str, reason: str="") -> None:
        with connect() as c: c.execute("""INSERT INTO configuration_locks(resource_type,resource_key,locked,actor,reason,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(resource_type,resource_key) DO UPDATE SET locked=excluded.locked,actor=excluded.actor,reason=excluded.reason,updated_at=excluded.updated_at""",(resource_type,resource_key,1 if locked else 0,actor,reason,now()))

    def is_locked(self, resource_type: str, resource_key: str) -> bool:
        with connect() as c: row=c.execute("SELECT locked FROM configuration_locks WHERE resource_type=? AND resource_key=?",(resource_type,resource_key)).fetchone()
        return bool(row and row[0])

    def snapshot_template(self, template: Any, actor: str, approval_state: str="Draft") -> int:
        payload=template.to_json() if hasattr(template,"to_json") else json.dumps(template,ensure_ascii=False,sort_keys=True)
        checksum=hashlib.sha256(payload.encode("utf-8")).hexdigest()
        key=getattr(template,"key",""); version=getattr(template,"version",""); lifecycle=getattr(template,"lifecycle","")
        with connect() as c:
            cur=c.execute("INSERT INTO template_version_snapshots(template_key,version,lifecycle,snapshot_json,checksum,actor,approval_state,created_at) VALUES(?,?,?,?,?,?,?,?)",(key,version,lifecycle,payload,checksum,actor,approval_state,now()))
            return int(cur.lastrowid)

    def list_versions(self, template_key: str | None=None, limit:int=100) -> list[dict[str,Any]]:
        q="SELECT id,template_key,version,lifecycle,checksum,actor,approval_state,created_at FROM template_version_snapshots"; args=[]
        if template_key: q+=" WHERE template_key=?"; args.append(template_key)
        q+=" ORDER BY id DESC LIMIT ?"; args.append(limit)
        with connect() as c: rows=c.execute(q,args).fetchall()
        return [dict(zip(["id","template_key","version","lifecycle","checksum","actor","approval_state","created_at"],r)) for r in rows]
