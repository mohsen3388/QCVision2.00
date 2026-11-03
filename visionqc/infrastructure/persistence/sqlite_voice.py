from __future__ import annotations
import json
from visionqc.application.ports.voice import VoiceConversationRepository
from visionqc.core.database import connect
from visionqc.voice.models import VoiceConversation, VoiceIntent, VoiceMessage


class SqliteVoiceConversationRepository(VoiceConversationRepository):
    def save(self, conversation: VoiceConversation) -> int:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO voice_conversations(conversation_uuid,title,factory_name,operator_name,selected_case_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (conversation.conversation_uuid, conversation.title, conversation.factory_name, conversation.operator_name, conversation.selected_case_id, conversation.created_at, conversation.updated_at),
            )
            cid = int(cur.lastrowid); self._replace_messages(conn, cid, conversation); return cid

    def update(self, conversation_id: int, conversation: VoiceConversation) -> None:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE voice_conversations SET title=?,factory_name=?,operator_name=?,selected_case_id=?,updated_at=? WHERE id=?",
                (conversation.title, conversation.factory_name, conversation.operator_name, conversation.selected_case_id, conversation.updated_at, conversation_id),
            )
            if cur.rowcount == 0: raise KeyError(f"Conversation {conversation_id} was not found")
            self._replace_messages(conn, conversation_id, conversation)

    def get(self, conversation_id: int) -> VoiceConversation | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM voice_conversations WHERE id=?", (conversation_id,)).fetchone()
            return self._hydrate(conn, row) if row else None

    def list_recent(self, limit: int = 50) -> list[tuple[int, VoiceConversation]]:
        with connect() as conn:
            rows = conn.execute("SELECT * FROM voice_conversations ORDER BY updated_at DESC,id DESC LIMIT ?", (limit,)).fetchall()
            return [(int(r["id"]), self._hydrate(conn, r)) for r in rows]

    @staticmethod
    def _replace_messages(conn, conversation_id: int, conversation: VoiceConversation) -> None:
        conn.execute("DELETE FROM voice_messages WHERE conversation_id=?", (conversation_id,))
        conn.executemany(
            "INSERT INTO voice_messages(conversation_id,message_uuid,role,text,intent,confidence,source,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            [(conversation_id,m.message_uuid,m.role,m.text,str(m.intent),m.confidence,m.source,json.dumps(m.metadata,ensure_ascii=False),m.created_at) for m in conversation.messages],
        )

    @staticmethod
    def _hydrate(conn, row) -> VoiceConversation:
        msgs = [VoiceMessage(
            message_uuid=m["message_uuid"], role=m["role"], text=m["text"], intent=VoiceIntent(m["intent"]),
            confidence=float(m["confidence"]), source=m["source"], metadata=json.loads(m["metadata_json"] or "{}"), created_at=m["created_at"],
        ) for m in conn.execute("SELECT * FROM voice_messages WHERE conversation_id=? ORDER BY id", (int(row["id"]),))]
        return VoiceConversation(
            conversation_uuid=row["conversation_uuid"], title=row["title"], factory_name=row["factory_name"] or "",
            operator_name=row["operator_name"] or "", selected_case_id=row["selected_case_id"], messages=msgs,
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
