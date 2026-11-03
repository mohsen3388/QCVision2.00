from __future__ import annotations

from collections import defaultdict, deque
from difflib import SequenceMatcher

from visionqc.application.ports.event_bus import EventBus
from visionqc.application.ports.knowledge_graph import KnowledgeGraphRepository
from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.domain.events import DomainEvent
from visionqc.domain.knowledge_graph import GraphPath, GraphSummary, KnowledgeEdge, KnowledgeNode, NodeType


class KnowledgeGraphService:
    """Offline graph of factory entities and QC-verified relationships."""

    def __init__(self, repository: KnowledgeGraphRepository, memory: FactoryMemoryService, event_bus: EventBus) -> None:
        self._repository = repository
        self._memory = memory
        self._event_bus = event_bus

    def rebuild_from_factory_memory(self, limit: int = 10000) -> GraphSummary:
        self._repository.clear_generated()
        cases = list(reversed(self._memory.list_recent(limit)))
        for case in cases:
            verified = bool(case.qc_approved)
            entities: dict[NodeType, int] = {}
            def add(t: NodeType, value: str) -> None:
                if value and value.strip():
                    canonical = self.canonicalize(t, value)
                    entities[t] = self._repository.upsert_node(t, canonical, value, verified=verified)
                    self._repository.upsert_alias(t, value, canonical)
            add(NodeType.PRODUCT, case.product_name)
            add(NodeType.MACHINE, case.production.machine_name)
            add(NodeType.LINE, case.production.production_line)
            add(NodeType.SHIFT, case.production.shift_name)
            add(NodeType.RECIPE, case.production.recipe_name)
            add(NodeType.SUPPLIER, case.production.supplier_name)
            add(NodeType.PROCESS_STAGE, case.production.process_stage)
            product_id = entities.get(NodeType.PRODUCT)
            for t, node_id in entities.items():
                if t != NodeType.PRODUCT and product_id:
                    self._repository.upsert_edge(product_id, node_id, f"RUNS_WITH_{t.value.upper()}", verified=verified)
            defect_ids=[]
            for defect in case.defects:
                canonical=self.canonicalize(NodeType.DEFECT, defect.defect_type)
                did=self._repository.upsert_node(NodeType.DEFECT,canonical,defect.defect_type,verified=verified)
                self._repository.upsert_alias(NodeType.DEFECT,defect.defect_type,canonical)
                defect_ids.append(did)
                if product_id: self._repository.upsert_edge(product_id,did,"HAS_DEFECT",weight=max(.2,defect.confidence or .6),verified=verified)
                for context_type in (NodeType.MACHINE,NodeType.LINE,NodeType.SHIFT,NodeType.RECIPE,NodeType.SUPPLIER,NodeType.PROCESS_STAGE):
                    if context_type in entities: self._repository.upsert_edge(entities[context_type],did,"ASSOCIATED_WITH_DEFECT",verified=verified)
            if case.confirmed_cause.strip():
                canonical=self.canonicalize(NodeType.CAUSE,case.confirmed_cause)
                cause_id=self._repository.upsert_node(NodeType.CAUSE,canonical,case.confirmed_cause,verified=verified)
                self._repository.upsert_alias(NodeType.CAUSE,case.confirmed_cause,canonical)
                for did in defect_ids: self._repository.upsert_edge(did,cause_id,"CAUSED_BY",weight=1.25 if verified else .6,verified=verified)
                for action in case.corrective_actions:
                    if not action.description.strip(): continue
                    ac=self.canonicalize(NodeType.ACTION,action.description)
                    aid=self._repository.upsert_node(NodeType.ACTION,ac,action.description,verified=bool(action.verified_by or action.result))
                    self._repository.upsert_alias(NodeType.ACTION,action.description,ac)
                    self._repository.upsert_edge(cause_id,aid,"MITIGATED_BY",weight=1.2 if action.result else .7,verified=bool(action.verified_by or action.result))
        summary=self._repository.summary()
        self._event_bus.publish(DomainEvent(name="knowledge_graph.rebuilt",source="knowledge_graph_service",payload={"nodes":summary.node_count,"edges":summary.edge_count,"verified_edges":summary.verified_edge_count}))
        return summary

    def canonicalize(self, node_type: NodeType, value: str) -> str:
        resolved=self._repository.resolve_alias(node_type,value)
        if node_type == NodeType.CAUSE:
            tokens=set(resolved.split())
            aliases={
                "worn cutter blade": ("worn cutter", "worn blade", "cutter blade worn", "damaged cutter blade"),
                "casing tension instability": ("casing tension", "wrong casing tension", "unstable casing tension"),
                "filling pressure instability": ("filling pressure", "unstable filling pressure", "low filling pressure"),
            }
            for canonical, variants in aliases.items():
                for variant in variants:
                    ratio=SequenceMatcher(None,resolved,variant).ratio()
                    overlap=len(tokens & set(variant.split()))/max(1,len(tokens | set(variant.split())))
                    if ratio>=.78 or overlap>=.67:
                        self._repository.upsert_alias(node_type,value,canonical)
                        return canonical
        return resolved

    def summary(self) -> GraphSummary:
        return self._repository.summary()

    def nodes(self, node_type: NodeType|None=None, limit: int=500) -> list[KnowledgeNode]:
        return self._repository.list_nodes(node_type,limit)

    def edges(self, node_id: int|None=None, limit: int=1000) -> list[KnowledgeEdge]:
        return self._repository.list_edges(node_id,limit)

    def related(self, node_id: int, limit: int=25) -> list[tuple[KnowledgeNode,KnowledgeEdge]]:
        nodes={n.node_id:n for n in self._repository.list_nodes(limit=5000)}
        result=[]
        for edge in self._repository.list_edges(node_id,limit=limit*2):
            other=edge.target_id if edge.source_id==node_id else edge.source_id
            if other in nodes: result.append((nodes[other],edge))
        result.sort(key=lambda x:(x[1].verified_count,x[1].weight,x[1].occurrence_count),reverse=True)
        return result[:limit]

    def find_paths(self, start_id: int, target_type: NodeType, max_depth: int=3, limit: int=10) -> list[GraphPath]:
        nodes={n.node_id:n for n in self._repository.list_nodes(limit=5000)}
        edges=self._repository.list_edges(limit=10000)
        adjacency=defaultdict(list)
        for e in edges:
            adjacency[e.source_id].append((e.target_id,e)); adjacency[e.target_id].append((e.source_id,e))
        queue=deque([(start_id,[start_id],[])])
        paths=[]
        while queue and len(paths)<limit:
            current,node_path,edge_path=queue.popleft()
            if len(edge_path)>=max_depth: continue
            for nxt,edge in adjacency[current]:
                if nxt in node_path: continue
                np=node_path+[nxt]; ep=edge_path+[edge]
                node=nodes.get(nxt)
                if node and node.node_type==target_type:
                    score=sum(e.weight + .3*e.verified_count for e in ep)/len(ep)
                    explanation=" → ".join(nodes[n].display_name for n in np if n in nodes)
                    paths.append(GraphPath(tuple(nodes[n] for n in np if n in nodes),tuple(ep),score,explanation))
                queue.append((nxt,np,ep))
        return sorted(paths,key=lambda p:p.score,reverse=True)[:limit]
