from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class NodeType(StrEnum):
    PRODUCT = "Product"
    DEFECT = "Defect"
    CAUSE = "Cause"
    ACTION = "CorrectiveAction"
    MACHINE = "Machine"
    LINE = "ProductionLine"
    SHIFT = "Shift"
    RECIPE = "Recipe"
    SUPPLIER = "Supplier"
    PROCESS_STAGE = "ProcessStage"


@dataclass(frozen=True, slots=True)
class KnowledgeNode:
    node_id: int
    node_type: NodeType
    canonical_name: str
    display_name: str
    occurrence_count: int = 0
    verified_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeEdge:
    edge_id: int
    source_id: int
    target_id: int
    relation: str
    weight: float = 1.0
    occurrence_count: int = 1
    verified_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphPath:
    nodes: tuple[KnowledgeNode, ...]
    edges: tuple[KnowledgeEdge, ...]
    score: float
    explanation: str


@dataclass(frozen=True, slots=True)
class GraphSummary:
    node_count: int
    edge_count: int
    verified_edge_count: int
    node_counts: dict[str, int]
