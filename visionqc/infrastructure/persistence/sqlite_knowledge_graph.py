from __future__ import annotations

import json
import re
import unicodedata
from visionqc.application.ports.knowledge_graph import KnowledgeGraphRepository
from visionqc.core.database import connect
from visionqc.domain.knowledge_graph import GraphSummary, KnowledgeEdge, KnowledgeNode, NodeType


def normalize_term(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().strip()
    value = re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)
    tokens = [t for t in re.split(r"[\s_-]+", value) if t]
    replacements = {"blades":"blade", "cutters":"cutter", "tears":"tear", "wrinkles":"wrinkle", "seals":"seal"}
    return " ".join(replacements.get(t, t[:-1] if len(t)>4 and t.endswith("s") else t) for t in tokens)


class SqliteKnowledgeGraphRepository(KnowledgeGraphRepository):
    def __init__(self) -> None:
        with connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_graph_nodes(
              id INTEGER PRIMARY KEY AUTOINCREMENT, node_type TEXT NOT NULL,
              canonical_name TEXT NOT NULL, display_name TEXT NOT NULL,
              occurrence_count INTEGER NOT NULL DEFAULT 1, verified_count INTEGER NOT NULL DEFAULT 0,
              metadata_json TEXT NOT NULL DEFAULT '{}', UNIQUE(node_type, canonical_name));
            CREATE TABLE IF NOT EXISTS knowledge_graph_aliases(
              id INTEGER PRIMARY KEY AUTOINCREMENT, node_type TEXT NOT NULL,
              alias_normalized TEXT NOT NULL, canonical_name TEXT NOT NULL,
              UNIQUE(node_type, alias_normalized));
            CREATE TABLE IF NOT EXISTS knowledge_graph_edges(
              id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL, target_id INTEGER NOT NULL,
              relation TEXT NOT NULL, weight REAL NOT NULL DEFAULT 1.0,
              occurrence_count INTEGER NOT NULL DEFAULT 1, verified_count INTEGER NOT NULL DEFAULT 0,
              metadata_json TEXT NOT NULL DEFAULT '{}', UNIQUE(source_id,target_id,relation));
            CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON knowledge_graph_nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON knowledge_graph_edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON knowledge_graph_edges(target_id);
            """)

    def clear_generated(self) -> None:
        with connect() as conn:
            conn.execute("DELETE FROM knowledge_graph_edges")
            conn.execute("DELETE FROM knowledge_graph_nodes")

    def upsert_node(self, node_type: NodeType, canonical_name: str, display_name: str, *, verified: bool=False) -> int:
        canonical_name = normalize_term(canonical_name)
        with connect() as conn:
            conn.execute("""INSERT INTO knowledge_graph_nodes(node_type,canonical_name,display_name,occurrence_count,verified_count)
                VALUES(?,?,?,?,?) ON CONFLICT(node_type,canonical_name) DO UPDATE SET
                occurrence_count=occurrence_count+1, verified_count=verified_count+excluded.verified_count,
                display_name=CASE WHEN length(excluded.display_name)>length(display_name) THEN excluded.display_name ELSE display_name END""",
                (str(node_type), canonical_name, display_name.strip() or canonical_name, 1, int(verified)))
            row=conn.execute("SELECT id FROM knowledge_graph_nodes WHERE node_type=? AND canonical_name=?",(str(node_type),canonical_name)).fetchone()
            return int(row[0])

    def upsert_alias(self, node_type: NodeType, alias: str, canonical_name: str) -> None:
        with connect() as conn:
            conn.execute("""INSERT INTO knowledge_graph_aliases(node_type,alias_normalized,canonical_name) VALUES(?,?,?)
             ON CONFLICT(node_type,alias_normalized) DO UPDATE SET canonical_name=excluded.canonical_name""",
             (str(node_type), normalize_term(alias), normalize_term(canonical_name)))

    def resolve_alias(self, node_type: NodeType, value: str) -> str:
        normalized=normalize_term(value)
        with connect() as conn:
            row=conn.execute("SELECT canonical_name FROM knowledge_graph_aliases WHERE node_type=? AND alias_normalized=?",(str(node_type),normalized)).fetchone()
        return str(row[0]) if row else normalized

    def upsert_edge(self, source_id: int, target_id: int, relation: str, *, weight: float=1.0, verified: bool=False) -> int:
        with connect() as conn:
            conn.execute("""INSERT INTO knowledge_graph_edges(source_id,target_id,relation,weight,occurrence_count,verified_count)
             VALUES(?,?,?,?,1,?) ON CONFLICT(source_id,target_id,relation) DO UPDATE SET
             occurrence_count=occurrence_count+1, verified_count=verified_count+excluded.verified_count,
             weight=weight+excluded.weight""",(source_id,target_id,relation,float(weight),int(verified)))
            row=conn.execute("SELECT id FROM knowledge_graph_edges WHERE source_id=? AND target_id=? AND relation=?",(source_id,target_id,relation)).fetchone()
            return int(row[0])

    def list_nodes(self, node_type: NodeType|None=None, limit: int=500) -> list[KnowledgeNode]:
        with connect() as conn:
            rows=conn.execute("SELECT * FROM knowledge_graph_nodes WHERE node_type=? ORDER BY verified_count DESC,occurrence_count DESC LIMIT ?",(str(node_type),limit)).fetchall() if node_type else conn.execute("SELECT * FROM knowledge_graph_nodes ORDER BY verified_count DESC,occurrence_count DESC LIMIT ?",(limit,)).fetchall()
        return [KnowledgeNode(int(r['id']),NodeType(r['node_type']),r['canonical_name'],r['display_name'],int(r['occurrence_count']),int(r['verified_count']),json.loads(r['metadata_json'] or '{}')) for r in rows]

    def list_edges(self, node_id: int|None=None, limit: int=1000) -> list[KnowledgeEdge]:
        with connect() as conn:
            rows=conn.execute("SELECT * FROM knowledge_graph_edges WHERE source_id=? OR target_id=? ORDER BY verified_count DESC,weight DESC LIMIT ?",(node_id,node_id,limit)).fetchall() if node_id else conn.execute("SELECT * FROM knowledge_graph_edges ORDER BY verified_count DESC,weight DESC LIMIT ?",(limit,)).fetchall()
        return [KnowledgeEdge(int(r['id']),int(r['source_id']),int(r['target_id']),r['relation'],float(r['weight']),int(r['occurrence_count']),int(r['verified_count']),json.loads(r['metadata_json'] or '{}')) for r in rows]

    def summary(self) -> GraphSummary:
        with connect() as conn:
            n=int(conn.execute("SELECT count(*) FROM knowledge_graph_nodes").fetchone()[0]); e=int(conn.execute("SELECT count(*) FROM knowledge_graph_edges").fetchone()[0]); v=int(conn.execute("SELECT count(*) FROM knowledge_graph_edges WHERE verified_count>0").fetchone()[0])
            counts={r[0]:int(r[1]) for r in conn.execute("SELECT node_type,count(*) FROM knowledge_graph_nodes GROUP BY node_type")}
        return GraphSummary(n,e,v,counts)
