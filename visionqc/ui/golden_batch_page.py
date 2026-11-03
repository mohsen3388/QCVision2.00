from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from visionqc.analysis.golden import build_reference, compare_to_reference
from visionqc.core.exporter import export_json
from visionqc.core.golden_repository import (create_profile, deactivate_profile, get_references,
    initialize_golden_tables, list_profiles, save_comparison)
from visionqc.models.results import AnalysisResult
from visionqc.ui.roi_label import RoiImageLabel
from visionqc.ui.widgets import MetricCard
from visionqc.ui.worker import AnalysisWorker


class GoldenBatchPage(QWidget):
    """Create approved visual references and compare production images against them."""
    def __init__(self) -> None:
        super().__init__(); initialize_golden_tables()
        self.image_path: str | None = None; self.result: AnalysisResult | None = None
        self.approved_samples: list[AnalysisResult] = []; self.comparison = None
        self.thread: QThread | None = None; self.worker = None
        self._build(); self.refresh_profiles()

    def _build(self):
        root=QVBoxLayout(self)
        title=QLabel("Golden Batch"); title.setObjectName("PageTitle")
        sub=QLabel("Build approved visual signatures from known-good samples and compare current production with explainable deviations."); sub.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(sub)
        tabs=QTabWidget(); root.addWidget(tabs,1)
        tabs.addTab(self._comparison_tab(),"Compare Production")
        tabs.addTab(self._profile_tab(),"Create & Manage Profiles")
        tabs.addTab(self._method_tab(),"Method & Safety")

    def _comparison_tab(self):
        page=QWidget(); root=QVBoxLayout(page)
        bar=QHBoxLayout(); self.profile_combo=QComboBox(); self.profile_combo.setMinimumWidth(300)
        self.load_btn=QPushButton("Load Current Image"); self.analyze_btn=QPushButton("Analyze & Compare")
        self.export_btn=QPushButton("Export Comparison JSON"); self.export_btn.setObjectName("Secondary"); self.export_btn.setEnabled(False)
        bar.addWidget(QLabel("Approved profile:")); bar.addWidget(self.profile_combo,1); bar.addWidget(self.load_btn); bar.addWidget(self.analyze_btn); bar.addWidget(self.export_btn); root.addLayout(bar)
        splitter=QSplitter(Qt.Orientation.Horizontal)
        left=QFrame(); left.setObjectName("Card"); ll=QVBoxLayout(left); self.image=RoiImageLabel(); self.image_info=QLabel("No current image"); self.image_info.setObjectName("Muted"); ll.addWidget(self.image,1); ll.addWidget(self.image_info)
        right=QWidget(); rl=QVBoxLayout(right); cards=QGridLayout(); self.sim=MetricCard("Golden Similarity"); self.conf=MetricCard("Comparison Confidence"); self.state=MetricCard("Decision Support Status"); self.dev=MetricCard("Out-of-range Metrics")
        for i,c in enumerate((self.sim,self.conf,self.state,self.dev)): cards.addWidget(c,i//2,i%2)
        rl.addLayout(cards); self.summary=QTextEdit(); self.summary.setReadOnly(True); rl.addWidget(self.summary)
        self.dev_table=QTableWidget(0,8); self.dev_table.setHorizontalHeaderLabels(["Group","Metric","Current","Golden Mean","Tolerance","Deviation","Similarity","Status"]); self.dev_table.horizontalHeader().setStretchLastSection(True); rl.addWidget(self.dev_table,1)
        splitter.addWidget(left); splitter.addWidget(right); splitter.setSizes([540,900]); root.addWidget(splitter,1)
        self.load_btn.clicked.connect(self.load_current); self.analyze_btn.clicked.connect(self.analyze_current); self.export_btn.clicked.connect(self.export_comparison)
        return page

    def _profile_tab(self):
        page=QWidget(); root=QVBoxLayout(page)
        form_frame=QFrame(); form_frame.setObjectName("Card"); form=QFormLayout(form_frame)
        self.p_name=QLineEdit(); self.p_product=QLineEdit(); self.p_stage=QComboBox(); self.p_stage.addItems(["Preparation","Mixing","Homogenization","Stable","Finished"]); self.p_line=QLineEdit(); self.p_desc=QTextEdit(); self.p_desc.setMaximumHeight(80)
        form.addRow("Profile name*",self.p_name); form.addRow("Product / recipe*",self.p_product); form.addRow("Process stage*",self.p_stage); form.addRow("Production line",self.p_line); form.addRow("Approval notes",self.p_desc)
        root.addWidget(form_frame)
        sample_row=QHBoxLayout(); self.add_sample=QPushButton("Analyze Approved Sample"); self.clear_samples=QPushButton("Clear Pending Samples"); self.clear_samples.setObjectName("Secondary"); self.create_btn=QPushButton("Create Golden Profile"); self.sample_label=QLabel("Pending approved samples: 0")
        sample_row.addWidget(self.add_sample); sample_row.addWidget(self.clear_samples); sample_row.addWidget(self.sample_label,1); sample_row.addWidget(self.create_btn); root.addLayout(sample_row)
        self.profile_table=QTableWidget(0,7); self.profile_table.setHorizontalHeaderLabels(["ID","Name","Product","Stage","Line","Samples","Updated"]); self.profile_table.horizontalHeader().setStretchLastSection(True); root.addWidget(self.profile_table,1)
        manage=QHBoxLayout(); refresh=QPushButton("Refresh Profiles"); deactivate=QPushButton("Deactivate Selected"); deactivate.setObjectName("Secondary"); manage.addWidget(refresh); manage.addWidget(deactivate); manage.addStretch(); root.addLayout(manage)
        self.add_sample.clicked.connect(self.add_approved_sample); self.clear_samples.clicked.connect(self._clear_samples); self.create_btn.clicked.connect(self.create_profile); refresh.clicked.connect(self.refresh_profiles); deactivate.clicked.connect(self.deactivate_selected)
        return page

    def _method_tab(self):
        text=QTextEdit(); text.setReadOnly(True); text.setPlainText(
            "Golden Batch method\n\n"
            "1. A qualified user selects several images from an accepted product, process stage and camera setup.\n"
            "2. VisionQC builds a visual signature using robust image-quality, color, texture and surface indicators.\n"
            "3. A current image is analyzed by the same engine. Each selected indicator is compared with the approved mean and tolerance.\n"
            "4. The overall score is weighted, while the strongest deviations remain visible for traceability.\n\n"
            "Recommended validation\n"
            "• Use at least 5–10 approved samples captured under the same lighting, distance, angle and process stage.\n"
            "• Create separate profiles for different recipes, stages, lines or camera installations.\n"
            "• Reapprove a profile after lighting, lens, vessel, recipe or process changes.\n\n"
            "Safety position\n"
            "A visual match is decision support, not proof of microbiological, chemical or regulatory conformity. Final acceptance remains with qualified QC personnel and required laboratory/HACCP controls.")
        return text

    def refresh_profiles(self):
        rows=list_profiles(); self.profile_combo.clear(); self.profile_table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            self.profile_combo.addItem(f"{r['name']} — {r['product_name']} / {r['process_stage']}",r['id'])
            vals=[r['id'],r['name'],r['product_name'],r['process_stage'],r['production_line'] or "",r['sample_count'],r['updated_at']]
            for j,v in enumerate(vals): self.profile_table.setItem(i,j,QTableWidgetItem(str(v)))
        self.profile_table.resizeColumnsToContents()

    def load_current(self):
        path,_=QFileDialog.getOpenFileName(self,"Select production image","","Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if not path:return
        pix=QPixmap(path)
        if pix.isNull(): QMessageBox.warning(self,"Invalid image","Image could not be displayed."); return
        self.image_path=path; self.image.set_source_pixmap(pix); self.image_info.setText(Path(path).name); self.result=None; self.comparison=None; self.export_btn.setEnabled(False)

    def analyze_current(self):
        if not self.image_path: QMessageBox.information(self,"Current image required","Load a current production image first."); return
        if self.profile_combo.currentData() is None: QMessageBox.information(self,"Golden profile required","Create or select an approved profile first."); return
        self._run_analysis(self.image_path,self.image.image_roi(),self._comparison_ready)

    def _run_analysis(self,path,roi,callback):
        for b in (self.load_btn,self.analyze_btn,self.add_sample,self.create_btn): b.setEnabled(False)
        self.thread=QThread(self); self.worker=AnalysisWorker(path,roi); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.completed.connect(callback); self.worker.failed.connect(lambda m: QMessageBox.critical(self,"Analysis failed",m)); self.worker.finished.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater); self.thread.finished.connect(lambda:[b.setEnabled(True) for b in (self.load_btn,self.analyze_btn,self.add_sample,self.create_btn)]); self.thread.start()

    def _comparison_ready(self,result):
        self.result=result; pid=int(self.profile_combo.currentData()); name=self.profile_combo.currentText().split(" — ")[0]
        try: self.comparison=compare_to_reference(result,pid,name,get_references(pid))
        except ValueError as exc: QMessageBox.warning(self,"Comparison unavailable",str(exc)); return
        save_comparison(self.comparison,result.source_path); self._render_comparison(); self.export_btn.setEnabled(True)

    def _render_comparison(self):
        c=self.comparison; out=sum(d.status=="Out of Range" for d in c.deviations)
        self.sim.set_value(f"{c.similarity_score:.1f}%"); self.conf.set_value(f"{c.confidence:.1f}%"); self.state.set_value(c.status); self.dev.set_value(str(out))
        lines=[f"Profile: {c.profile_name}",f"Status: {c.status}",f"Golden similarity: {c.similarity_score:.2f}%",f"Confidence: {c.confidence:.2f}%","",c.recommendation,"","Strongest deviations:"]
        for d in c.strongest_deviations: lines.append(f"• {d.metric.replace('_',' ').title()}: current {d.current:.3f}, golden {d.reference_mean:.3f}, {d.status}")
        self.summary.setPlainText("\n".join(lines)); self.dev_table.setRowCount(len(c.deviations))
        for i,d in enumerate(sorted(c.deviations,key=lambda x:x.normalized_deviation,reverse=True)):
            vals=[d.group,d.metric.replace('_',' ').title(),f"{d.current:.3f}",f"{d.reference_mean:.3f}",f"±{getattr(next((r for r in get_references(c.profile_id) if r.metric==d.metric),None),'tolerance',0):.3f}",f"{d.normalized_deviation:.2f}×",f"{d.similarity:.1f}%",d.status]
            for j,v in enumerate(vals): self.dev_table.setItem(i,j,QTableWidgetItem(v))
        self.dev_table.resizeColumnsToContents()

    def add_approved_sample(self):
        path,_=QFileDialog.getOpenFileName(self,"Select approved sample","","Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if path:self._run_analysis(path,None,self._approved_ready)
    def _approved_ready(self,result):
        if result.status=="Review Required":
            if QMessageBox.question(self,"Low-quality approved sample","This sample has Review Required status. Add it to the pending Golden profile anyway?")!=QMessageBox.StandardButton.Yes:return
        self.approved_samples.append(result); self.sample_label.setText(f"Pending approved samples: {len(self.approved_samples)}")
    def _clear_samples(self): self.approved_samples.clear(); self.sample_label.setText("Pending approved samples: 0")

    def create_profile(self):
        name=self.p_name.text().strip(); product=self.p_product.text().strip()
        if not name or not product: QMessageBox.information(self,"Required information","Profile name and product are required."); return
        if not self.approved_samples: QMessageBox.information(self,"Approved samples required","Analyze at least one accepted sample. Five or more are recommended."); return
        try: refs=build_reference(self.approved_samples); create_profile(name,product,self.p_stage.currentText(),self.p_line.text().strip(),self.p_desc.toPlainText().strip(),refs,self.approved_samples)
        except Exception as exc: QMessageBox.critical(self,"Profile creation failed",str(exc)); return
        QMessageBox.information(self,"Golden profile created",f"'{name}' was created from {len(self.approved_samples)} approved sample(s).")
        self._clear_samples(); self.p_name.clear(); self.p_product.clear(); self.p_line.clear(); self.p_desc.clear(); self.refresh_profiles()

    def deactivate_selected(self):
        row=self.profile_table.currentRow()
        if row<0:return
        pid=int(self.profile_table.item(row,0).text()); name=self.profile_table.item(row,1).text()
        if QMessageBox.question(self,"Deactivate profile",f"Deactivate '{name}'? Historical comparisons will be retained.")==QMessageBox.StandardButton.Yes:
            deactivate_profile(pid); self.refresh_profiles()

    def export_comparison(self):
        if not self.comparison:return
        path,_=QFileDialog.getSaveFileName(self,"Export comparison",f"golden_comparison_{self.comparison.profile_id}.json","JSON (*.json)")
        if path: export_json(self.comparison,path); QMessageBox.information(self,"Export complete",path)
