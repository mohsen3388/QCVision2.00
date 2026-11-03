from __future__ import annotations

from collections import deque
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout, QWidget


class Sparkline(QWidget):
    def __init__(self):
        super().__init__(); self.values=[]; self.setFixedSize(82, 24)
    def set_values(self, values): self.values=list(values)[-60:]; self.update()
    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); r=self.rect().adjusted(1,2,-1,-2)
        p.fillRect(self.rect(), QColor("#f4f7f8")); p.setPen(QPen(QColor("#d6e0e5"),1)); p.drawLine(r.left(),r.center().y(),r.right(),r.center().y())
        if len(self.values)<2:return
        v=self.values; color=QColor("#2f855a" if v[-1]>=85 else "#b7791f" if v[-1]>=70 else "#c05621" if v[-1]>=55 else "#c53030")
        p.setPen(QPen(color,1.8)); n=len(v)
        pts=[]
        for i,x in enumerate(v): pts.append((r.left()+i*r.width()/max(1,n-1), r.bottom()-max(0,min(100,x))*r.height()/100))
        for a,b in zip(pts,pts[1:]): p.drawLine(int(a[0]),int(a[1]),int(b[0]),int(b[1]))

class IndicatorItem(QFrame):
    def __init__(self,title):
        super().__init__(); self.setObjectName("IndicatorItem"); self.history=deque(maxlen=60)
        lay=QHBoxLayout(self); lay.setContentsMargins(6,3,6,3); lay.setSpacing(5)
        self.title=QLabel(title); self.title.setMinimumWidth(92); self.value=QLabel("—"); self.value.setMinimumWidth(35); self.value.setAlignment(Qt.AlignmentFlag.AlignCenter); self.trend=QLabel("→"); self.spark=Sparkline()
        lay.addWidget(self.title); lay.addWidget(self.value); lay.addWidget(self.trend); lay.addWidget(self.spark)
    def update_score(self,score):
        old=self.history[-1] if self.history else score; self.history.append(float(score)); self.spark.set_values(self.history)
        self.value.setText(f"{score:.0f}"); delta=score-old; self.trend.setText("↑" if delta>1 else "↓" if delta<-1 else "→")
        color="#2f855a" if score>=85 else "#b7791f" if score>=70 else "#c05621" if score>=55 else "#c53030"
        self.value.setStyleSheet(f"font-weight:700;color:{color};")

class QualityIndicatorDashboard(QFrame):
    def __init__(self):
        super().__init__(); self.setObjectName("Card"); outer=QHBoxLayout(self); outer.setContentsMargins(8,6,8,6)
        grid=QGridLayout(); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(3); self.items={}
        titles=[("image","کیفیت تصویر"),("color","ثبات رنگ"),("texture","یکنواختی بافت"),("surface","سلامت سطح"),("aeration","سلامت هوادهی"),("motion","ثبات حرکت"),("mixing","پوشش اختلاط"),("reference","تطابق با مرجع"),("process","ثبات فرایند"),("lighting","نوردهی"),("focus","وضوح تصویر"),("risk","کنترل ریسک")]
        for i,(key,title) in enumerate(titles):
            item=IndicatorItem(title); self.items[key]=item; grid.addWidget(item,i//3,i%3)
        left=QVBoxLayout(); hdr=QLabel("نبض کیفیت — روند ۲ دقیقه اخیر"); hdr.setStyleSheet("font-weight:700;"); left.addWidget(hdr); left.addLayout(grid); outer.addLayout(left,4)
        box=QVBoxLayout(); ah=QLabel("پیشنهادهای تخصصی"); ah.setStyleSheet("font-weight:700;"); self.advisor=QTextEdit(); self.advisor.setReadOnly(True); self.advisor.setMaximumHeight(155); self.advisor.setPlaceholderText("پیشنهادهای الگوریتم و هوش مصنوعی در این بخش نمایش داده می‌شوند."); box.addWidget(ah); box.addWidget(self.advisor); outer.addLayout(box,2)
        self.setMaximumHeight(235)
    def update_scores(self,scores,recommendations=None,ai_text=""):
        for x in scores:
            if x.key in self.items:self.items[x.key].update_score(x.score)
        lines=[]
        if recommendations: lines.extend([f"• {x}" for x in recommendations])
        if ai_text: lines.extend(["", "نظر هوش مصنوعی:", ai_text.strip()])
        if lines:self.advisor.setPlainText("\n".join(lines))
    def reset(self):
        for item in self.items.values(): item.history.clear(); item.value.setText("—"); item.trend.setText("→"); item.spark.set_values([])
        self.advisor.clear()
