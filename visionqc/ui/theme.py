from __future__ import annotations

THEMES = {
    "Factory Blue": {
        "bg":"#f5f7fa","fg":"#243240","sidebar":"#17324d","sidebar_fg":"#dce8f2","card":"#ffffff","border":"#dfe6ec","primary":"#286f9f","primary_hover":"#205c84","accent":"#f4b942","muted":"#687681","header":"#eaf1f6","secondary":"#e5edf3"
    },
    "Dark": {
        "bg":"#151a1f","fg":"#e7edf2","sidebar":"#0d2234","sidebar_fg":"#dce8f2","card":"#202830","border":"#394550","primary":"#3b8bc2","primary_hover":"#4a9bd2","accent":"#e8b64a","muted":"#aeb9c1","header":"#29343d","secondary":"#313d47"
    },
    "High Contrast": {
        "bg":"#000000","fg":"#ffffff","sidebar":"#000000","sidebar_fg":"#ffffff","card":"#000000","border":"#ffffff","primary":"#005fcc","primary_hover":"#1b7cff","accent":"#ffd400","muted":"#ffffff","header":"#111111","secondary":"#222222"
    },
}


def stylesheet_for(theme_name: str) -> str:
    c = THEMES.get(theme_name, THEMES["Factory Blue"])
    return f"""
QMainWindow, QWidget {{ background:{c['bg']}; color:{c['fg']}; font-family:'Segoe UI'; font-size:10pt; }}
QFrame#Sidebar {{ background:{c['sidebar']}; border:0; }} QLabel#Brand {{ color:white; font-size:20pt; font-weight:700; padding:18px; }}
QLabel#SidebarContext {{ color:#9fc2dc; padding:0 18px 10px 18px; font-size:9pt; }}
QPushButton#NavButton {{ color:{c['sidebar_fg']}; text-align:left; padding:12px 18px; border:0; border-radius:6px; background:transparent; }}
QPushButton#NavButton:hover {{ background:{c['primary']}; }} QPushButton#NavButton:checked {{ background:{c['primary']}; color:white; font-weight:600; }}
QPushButton#FeatureMenuButton, QPushButton#MenuPrimary {{ background:{c['accent']}; color:#17324d; font-weight:800; padding:12px; border-radius:7px; }}
QFrame#Card, QFrame#FeatureCard {{ background:{c['card']}; border:1px solid {c['border']}; border-radius:10px; }}
QFrame#FeatureCard {{ min-width:250px; min-height:145px; }} QLabel#CardTitle {{ color:{c['muted']}; font-size:9pt; }} QLabel#CardValue {{ color:{c['fg']}; font-size:22pt; font-weight:700; }}
QLabel#PageTitle {{ font-size:22pt; font-weight:700; color:{c['fg']}; }} QLabel#PageSubtitle, QLabel#Muted {{ color:{c['muted']}; }}
QLabel#SectionTitle {{ font-size:14pt; font-weight:700; color:{c['fg']}; margin-top:12px; }} QLabel#FeatureTitle {{ font-size:12pt; font-weight:700; color:{c['fg']}; }}
QLabel#FeatureDescription {{ color:{c['muted']}; }} QLabel#Badge_available {{ background:#dff2e3;color:#1b6c31;padding:4px 7px;border-radius:8px;font-weight:700; }}
QLabel#Badge_next {{ background:#fff0cf;color:#8a5b00;padding:4px 7px;border-radius:8px;font-weight:700; }} QLabel#Badge_planned {{ background:#e7edf3;color:#526574;padding:4px 7px;border-radius:8px;font-weight:700; }}
QLabel#InfoPanel {{ background:{c['card']}; border:1px solid {c['border']}; padding:18px; border-radius:10px; }}
QPushButton {{ background:{c['primary']}; color:white; border:0; border-radius:6px; padding:9px 14px; font-weight:600; }}
QPushButton:hover {{ background:{c['primary_hover']}; }} QPushButton:disabled {{ background:#77838c; }} QPushButton#Secondary {{ background:{c['secondary']}; color:{c['fg']}; }}
QProgressBar {{ border:1px solid {c['border']}; border-radius:5px; text-align:center; background:{c['card']}; }} QProgressBar::chunk {{ background:{c['primary']}; border-radius:4px; }}
QTableWidget, QTreeWidget, QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background:{c['card']}; color:{c['fg']}; border:1px solid {c['border']}; selection-background-color:{c['primary']}; }}
QHeaderView::section {{ background:{c['header']}; color:{c['fg']}; padding:7px; border:0; font-weight:600; }} QTabWidget::pane {{ border:1px solid {c['border']}; background:{c['card']}; }}
QTabBar::tab {{ background:{c['secondary']}; color:{c['fg']}; padding:9px 14px; }} QTabBar::tab:selected {{ background:{c['card']}; font-weight:600; }}
QMenuBar, QMenu {{ background:{c['card']}; color:{c['fg']}; }} QMenu::item:selected {{ background:{c['primary']}; color:white; }}
"""

APP_STYLESHEET = stylesheet_for("Factory Blue")
