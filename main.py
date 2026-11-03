from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime

from PySide6.QtWidgets import QApplication, QMessageBox

from visionqc.bootstrap import bootstrap_application
from visionqc.core.settings import APP_NAME, ORGANIZATION_NAME, app_data_dir
from visionqc.runtime import set_application_context
from visionqc.ui.first_run_wizard import FirstRunWizard
from visionqc.ui.main_window import MainWindow
from visionqc.ui.theme import stylesheet_for

logger = logging.getLogger(__name__)


def _install_crash_handler(commercial_service=None) -> None:
    def handler(exc_type, exc, tb):
        path = app_data_dir() / "crash.log"
        with path.open("a", encoding="utf-8") as file:
            file.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n")
            traceback.print_exception(exc_type, exc, tb, file=file)
        logger.critical("Unhandled application error", exc_info=(exc_type, exc, tb))
        if commercial_service is not None:
            try:
                commercial_service.record_crash(exc_type, exc, "".join(traceback.format_exception(exc_type, exc, tb)))
            except Exception:
                logger.exception("Could not write structured crash report")
        QMessageBox.critical(None, "VisionQC error", f"An unexpected error occurred.\nA local diagnostic log was written to:\n{path}")
    sys.excepthook = handler


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION_NAME)
    context = bootstrap_application()
    _install_crash_handler(context.container.resolve("commercial_edition_service"))
    set_application_context(context)
    settings = context.settings
    scale = int(settings.get("ui_scale", 100))
    app.setStyleSheet(stylesheet_for(settings.get("theme", "Factory Blue")) + f"\nQWidget{{font-size:{max(9, round(10 * scale / 100))}pt;}}")

    if not settings.get("first_run_complete", False):
        wizard = FirstRunWizard()
        if wizard.exec() == 0:
            return 0

    window = MainWindow(context=context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
