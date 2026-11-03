from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QTextEdit, QVBoxLayout, QWidget


class GeminiReviewPanel(QWidget):
    """Two-stage Gemini view: concise QC summary plus collapsed technical detail."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlaceholderText("The concise English QC summary will appear here.")

        self.toggle = QPushButton("Show Technical Report")
        self.toggle.setObjectName("Secondary")
        self.toggle.setCheckable(True)
        self.toggle.setEnabled(False)

        self.technical = QTextEdit()
        self.technical.setReadOnly(True)
        self.technical.setVisible(False)

        layout.addWidget(self.summary, 1)
        layout.addWidget(self.toggle)
        layout.addWidget(self.technical, 1)
        self.toggle.toggled.connect(self._toggle_technical)

    def set_reports(self, summary: str, technical: str) -> None:
        self.summary.setPlainText(summary)
        self.technical.setPlainText(technical)
        self.toggle.setEnabled(bool(technical.strip()))
        self.toggle.setChecked(False)
        self.technical.setVisible(False)
        self.toggle.setText("Show Technical Report")

    def setPlainText(self, text: str) -> None:
        """Compatibility method for existing callers."""
        self.set_reports(text, text)

    def clear(self) -> None:
        self.summary.clear()
        self.technical.clear()
        self.toggle.setChecked(False)
        self.toggle.setEnabled(False)
        self.technical.setVisible(False)
        self.toggle.setText("Show Technical Report")

    def _toggle_technical(self, visible: bool) -> None:
        self.technical.setVisible(visible)
        self.toggle.setText("Hide Technical Report" if visible else "Show Technical Report")
