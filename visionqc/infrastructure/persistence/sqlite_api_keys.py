from __future__ import annotations
from datetime import datetime,timezone
import hashlib,secrets
from visionqc.core.database import connect

class SqliteApiKeyRepository:
    def initialize(self)->None:
        with connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS enterprise_api_keys(
              key_id TEXT PRIMARY KEY,name TEXT NOT NULL,key_hash TEXT NOT NULL UNIQUE,
              role TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,last_used_at TEXT);
            CREATE TABLE IF NOT EXISTS integration_settings(
              connector_id TEXT PRIMARY KEY,settings_json TEXT NOT NULL,updated_at TEXT NOT NULL);
            """)
    @staticmethod
    def _hash(secret:str)->str: return hashlib.sha256(secret.encode("utf-8")).hexdigest()
    def issue(self,name:str,role:str)->tuple[str,str]:
        self.initialize(); key_id=secrets.token_hex(6); secret="vqc_"+secrets.token_urlsafe(28); now=datetime.now(timezone.utc).isoformat()
        with connect() as conn: conn.execute("INSERT INTO enterprise_api_keys VALUES(?,?,?,?,?,?,?)",(key_id,name,self._hash(secret),role,1,now,None))
        return key_id,secret
    def authenticate(self,secret:str):
        self.initialize(); digest=self._hash(secret)
        with connect() as conn:
            row=conn.execute("SELECT key_id,name,role,enabled FROM enterprise_api_keys WHERE key_hash=?",(digest,)).fetchone()
            if not row or not int(row[3]): return None
            conn.execute("UPDATE enterprise_api_keys SET last_used_at=? WHERE key_id=?",(datetime.now(timezone.utc).isoformat(),row[0]))
            return {"key_id":row[0],"name":row[1],"role":row[2]}
    def disable(self,key_id:str)->None:
        self.initialize()
        with connect() as conn: conn.execute("UPDATE enterprise_api_keys SET enabled=0 WHERE key_id=?",(key_id,))
    def list_all(self):
        self.initialize()
        with connect() as conn:
            rows=conn.execute("SELECT key_id,name,role,enabled,created_at,last_used_at FROM enterprise_api_keys ORDER BY created_at DESC").fetchall()
        return [{"key_id":r[0],"name":r[1],"role":r[2],"enabled":bool(r[3]),"created_at":r[4],"last_used_at":r[5]} for r in rows]
