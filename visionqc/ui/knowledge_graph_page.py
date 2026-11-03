from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox,QHBoxLayout,QHeaderView,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget

from visionqc.application.services.knowledge_graph_service import KnowledgeGraphService
from visionqc.domain.knowledge_graph import NodeType


class KnowledgeGraphPage(QWidget):
    def __init__(self, service: KnowledgeGraphService) -> None:
        super().__init__(); self.service=service; self._nodes=[]; self._build(); self.refresh()

    def _build(self):
        layout=QVBoxLayout(self)
        title=QLabel("Factory Knowledge Graph"); title.setObjectName("pageTitle")
        sub=QLabel("Offline relationships learned from Factory Memory. Verified QC evidence is weighted above unverified observations."); sub.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(sub)
        row=QHBoxLayout(); self.type_combo=QComboBox(); self.type_combo.addItem("All node types",None)
        for t in NodeType: self.type_combo.addItem(t.value,t)
        self.type_combo.currentIndexChanged.connect(self.refresh)
        rebuild=QPushButton("Rebuild from Factory Memory"); rebuild.clicked.connect(self.rebuild)
        row.addWidget(QLabel("Entity type:")); row.addWidget(self.type_combo); row.addStretch(1); row.addWidget(rebuild); layout.addLayout(row)
        self.summary=QLabel(); layout.addWidget(self.summary)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["Type","Entity","Occurrences","QC verified","ID"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); self.table.itemSelectionChanged.connect(self.show_related)
        layout.addWidget(self.table,2)
        self.detail=QTextEdit(); self.detail.setReadOnly(True); self.detail.setPlaceholderText("Select an entity to inspect its strongest relationships."); layout.addWidget(self.detail,1)

    def rebuild(self):
        summary=self.service.rebuild_from_factory_memory(); self.refresh(); self.summary.setText(f"Graph rebuilt: {summary.node_count} nodes, {summary.edge_count} relationships, {summary.verified_edge_count} QC-verified relationships.")

    def refresh(self):
        t=self.type_combo.currentData() if hasattr(self,'type_combo') else None
        self._nodes=self.service.nodes(t,1000)
        self.table.setRowCount(len(self._nodes))
        for r,n in enumerate(self._nodes):
            vals=[n.node_type.value,n.display_name,str(n.occurrence_count),str(n.verified_count),str(n.node_id)]
            for c,v in enumerate(vals):
                item=QTableWidgetItem(v); item.setTextAlignment(Qt.AlignLeft|Qt.AlignVCenter if c==1 else Qt.AlignCenter); self.table.setItem(r,c,item)
        s=self.service.summary(); self.summary.setText(f"{s.node_count} entities | {s.edge_count} relationships | {s.verified_edge_count} verified relationships")

    def show_related(self):
        row=self.table.currentRow()
        if row<0 or row>=len(self._nodes): return
        node=self._nodes[row]; lines=[f"{node.node_type.value}: {node.display_name}",f"Occurrences: {node.occurrence_count} | QC verified: {node.verified_count}","","STRONGEST RELATIONSHIPS"]
        related=self.service.related(node.node_id,30)
        if not related: lines.append("No relationship has been learned yet. Rebuild after recording Factory Memory cases.")
        for other,edge in related:
            direction="→" if edge.source_id==node.node_id else "←"
            lines.append(f"• {direction} {edge.relation} {other.node_type.value}: {other.display_name} | occurrences {edge.occurrence_count}, verified {edge.verified_count}, weight {edge.weight:.2f}")
        self.detail.setPlainText("\n".join(lines))
