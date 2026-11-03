from __future__ import annotations

import json
from pathlib import Path

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QComboBox,QFileDialog,QFormLayout,QGroupBox,QHBoxLayout,QInputDialog,QLabel,QLineEdit,QListWidget,QMessageBox,QPushButton,QSpinBox,QDoubleSpinBox,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget)

from visionqc.core.inspection import (PipelineNode,ROI,batch_test,create_project,export_pipeline,export_project,get_project,import_images,list_images,list_projects,list_rois,load_pipeline,run_file,save_pipeline,save_roi)

class InspectionDesignerPage(QWidget):
    def __init__(self):
        super().__init__(); self.current_project_id=None; self.current_image=None; self.nodes=[]
        root=QVBoxLayout(self); title=QLabel('Visual Inspection Designer'); title.setObjectName('PageTitle'); root.addWidget(title)
        subtitle=QLabel('Build and test explainable offline image-inspection pipelines without programming.'); subtitle.setWordWrap(True); root.addWidget(subtitle)
        bar=QHBoxLayout(); self.projects=QComboBox(); self.projects.currentIndexChanged.connect(self._project_changed); bar.addWidget(QLabel('Project')); bar.addWidget(self.projects,1)
        for text,slot in [('New Project',self.new_project),('Import Images',self.import_folder),('Export Pipeline',self.export_pipeline_file),('Export Project',self.export_project_file)]:
            b=QPushButton(text); b.clicked.connect(slot); bar.addWidget(b)
        root.addLayout(bar)
        body=QHBoxLayout(); root.addLayout(body,1)
        left=QVBoxLayout(); body.addLayout(left,1)
        self.images=QListWidget(); self.images.currentTextChanged.connect(self.preview_image); left.addWidget(QLabel('Dataset')); left.addWidget(self.images,1)
        self.preview=QLabel('Select an image'); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumSize(480,360); self.preview.setStyleSheet('border:1px solid #777;'); left.addWidget(self.preview,3)
        roi_box=QGroupBox('ROI Designer'); rf=QFormLayout(roi_box); self.roi_name=QLineEdit('Main ROI'); self.x1=QSpinBox(); self.y1=QSpinBox(); self.x2=QSpinBox(); self.y2=QSpinBox()
        for w in (self.x1,self.y1,self.x2,self.y2): w.setRange(0,10000)
        self.x2.setValue(500); self.y2.setValue(500); rf.addRow('Name',self.roi_name); rf.addRow('X1',self.x1); rf.addRow('Y1',self.y1); rf.addRow('X2',self.x2); rf.addRow('Y2',self.y2); rb=QPushButton('Save Rectangle ROI'); rb.clicked.connect(self.save_rectangle_roi); rf.addRow(rb); left.addWidget(roi_box)
        right=QVBoxLayout(); body.addLayout(right,1)
        nodebar=QHBoxLayout(); self.node_type=QComboBox(); self.node_type.addItems(['gray','gaussian_blur','median_blur','threshold','adaptive_threshold','canny','morph_open','morph_close','erode','dilate','contours','measure','decision']); nodebar.addWidget(self.node_type,1); add=QPushButton('Add Node'); add.clicked.connect(self.add_node); nodebar.addWidget(add); right.addLayout(nodebar)
        self.node_list=QListWidget(); self.node_list.currentRowChanged.connect(self.show_params); right.addWidget(QLabel('Processing Pipeline')); right.addWidget(self.node_list,1)
        self.params=QTextEdit(); self.params.setPlaceholderText('{"kernel": 5}'); right.addWidget(QLabel('Selected node parameters (JSON)')); right.addWidget(self.params,1)
        controls=QHBoxLayout();
        for text,slot in [('Apply Params',self.apply_params),('Move Up',lambda:self.move_node(-1)),('Move Down',lambda:self.move_node(1)),('Delete',self.delete_node),('Save Pipeline',self.save_current_pipeline),('Run Image',self.run_current),('Batch Test',self.run_batch)]:
            b=QPushButton(text); b.clicked.connect(slot); controls.addWidget(b)
        right.addLayout(controls)
        self.results=QTableWidget(0,2); self.results.setHorizontalHeaderLabels(['Measurement','Value']); self.results.horizontalHeader().setStretchLastSection(True); right.addWidget(self.results,2)
        self.status=QLabel('Ready'); self.status.setWordWrap(True); right.addWidget(self.status)
        self.reload()

    def reload(self):
        current=self.current_project_id; self.projects.blockSignals(True); self.projects.clear()
        for p in list_projects(): self.projects.addItem(p['name'],p['id'])
        self.projects.blockSignals(False)
        if self.projects.count():
            idx=self.projects.findData(current) if current else 0; self.projects.setCurrentIndex(max(0,idx)); self._project_changed()

    def new_project(self):
        name,ok=QInputDialog.getText(self,'New Inspection Project','Project name')
        if ok and name.strip(): self.current_project_id=create_project(name); self.reload()

    def _project_changed(self):
        self.current_project_id=self.projects.currentData(); self.images.clear(); self.nodes=[]; self.node_list.clear()
        if not self.current_project_id:return
        for item in list_images(self.current_project_id): self.images.addItem(item['file_path'])
        self.nodes=load_pipeline(self.current_project_id); self.refresh_nodes()

    def import_folder(self):
        if not self.current_project_id:return
        path=QFileDialog.getExistingDirectory(self,'Import image folder')
        if path:
            imported=import_images(self.current_project_id,path); self._project_changed(); self.status.setText(f'Imported {len(imported)} images.')

    def preview_image(self,path):
        self.current_image=path or None
        if not path:return
        pix=QPixmap(path)
        self.preview.setPixmap(pix.scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))

    def add_node(self):
        defaults={'gaussian_blur':{'kernel':5,'sigma':0},'median_blur':{'kernel':5},'threshold':{'value':127,'inverse':False},'adaptive_threshold':{'block_size':11,'c':2},'canny':{'low':50,'high':150},'contours':{'min_area':20},'measure':{},'decision':{'rules':[{'metric':'area','operator':'>','value':5000,'fail_when':True}]}}
        t=self.node_type.currentText(); self.nodes.append(PipelineNode(t,defaults.get(t,{'kernel':3,'iterations':1}))); self.refresh_nodes(); self.node_list.setCurrentRow(len(self.nodes)-1)

    def refresh_nodes(self):
        self.node_list.clear()
        for i,n in enumerate(self.nodes): self.node_list.addItem(f'{i+1}. {n.node_type}')

    def show_params(self,row):
        if 0<=row<len(self.nodes): self.params.setPlainText(json.dumps(self.nodes[row].params,indent=2))

    def apply_params(self):
        row=self.node_list.currentRow()
        try:self.nodes[row].params=json.loads(self.params.toPlainText() or '{}'); self.status.setText('Parameters applied.')
        except Exception as e: QMessageBox.warning(self,'Invalid JSON',str(e))

    def move_node(self,d):
        i=self.node_list.currentRow(); j=i+d
        if 0<=i<len(self.nodes) and 0<=j<len(self.nodes): self.nodes[i],self.nodes[j]=self.nodes[j],self.nodes[i]; self.refresh_nodes(); self.node_list.setCurrentRow(j)

    def delete_node(self):
        i=self.node_list.currentRow()
        if 0<=i<len(self.nodes): self.nodes.pop(i); self.refresh_nodes()

    def save_current_pipeline(self):
        if self.current_project_id: save_pipeline(self.current_project_id,self.nodes); self.status.setText('Pipeline saved.')

    def save_rectangle_roi(self):
        if self.current_project_id:
            save_roi(self.current_project_id,ROI(self.roi_name.text(),'rectangle',[[self.x1.value(),self.y1.value()],[self.x2.value(),self.y2.value()]])); self.status.setText('ROI saved.')

    def run_current(self):
        if not self.current_project_id or not self.current_image:return
        self.save_current_pipeline()
        try:
            r=run_file(self.current_project_id,self.current_image); self.results.setRowCount(len(r.measurements))
            for i,(k,v) in enumerate(sorted(r.measurements.items())): self.results.setItem(i,0,QTableWidgetItem(k)); self.results.setItem(i,1,QTableWidgetItem(f'{v:.4f}'))
            self.status.setText(('PASS' if r.passed else 'REJECT')+f' | {r.processing_ms:.2f} ms'+((' | '+ '; '.join(r.reasons)) if r.reasons else ''))
            if r.overlay is not None:
                rgb=cv2.cvtColor(r.overlay,cv2.COLOR_BGR2RGB); h,w,c=rgb.shape; q=QImage(rgb.data,w,h,c*w,QImage.Format_RGB888).copy(); self.preview.setPixmap(QPixmap.fromImage(q).scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        except Exception as e: QMessageBox.critical(self,'Inspection failed',str(e))

    def run_batch(self):
        if not self.current_project_id:return
        self.save_current_pipeline(); paths=[self.images.item(i).text() for i in range(self.images.count())]
        try:
            s=batch_test(self.current_project_id,paths); self.status.setText(f"Batch: {s['total']} | PASS {s['passed']} ({s['pass_percent']:.1f}%) | REJECT {s['rejected']} | Avg {s['average_ms']:.2f} ms")
        except Exception as e: QMessageBox.critical(self,'Batch failed',str(e))

    def export_pipeline_file(self):
        if not self.current_project_id:return
        path,_=QFileDialog.getSaveFileName(self,'Export Pipeline','','VisionQC Pipeline (*.vqpipeline)')
        if path: export_pipeline(self.current_project_id,path); self.status.setText(f'Exported {path}')

    def export_project_file(self):
        if not self.current_project_id:return
        path,_=QFileDialog.getSaveFileName(self,'Export Project','','VisionQC Project (*.vqproject)')
        if path: export_project(self.current_project_id,path); self.status.setText(f'Exported {path}')
