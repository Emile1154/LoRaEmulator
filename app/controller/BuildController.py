import os
import subprocess
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QPlainTextEdit

_WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGE_NAME = "meshtastic-firmware-dev"


class BuildController(QObject):
    _log_line = pyqtSignal(str)

    def __init__(self, console: QPlainTextEdit | None = None):
        super().__init__()
        self._console = console
        self._log_line.connect(self._append_log)

    def set_console(self, console: QPlainTextEdit):
        self._console = console

    def _append_log(self, line: str):
        if self._console is None:
            return
        self._console.appendPlainText(line)
        sb = self._console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def rebuild_meshtastic(self):
        threading.Thread(
            target=self._do_build_meshtastic,
            daemon=True,
            name="meshtastic_build",
        ).start()

    def _do_build_meshtastic(self):
        self._log_line.emit("[Build] Starting Meshtastic firmware build...")

        proc = subprocess.Popen(
            [
                "docker", "run", "--rm",
                "--network=host",
                "-v", f"{_WORKSPACE}:/home/user/workspace:rw",
                "-w", "/home/user/workspace/meshtastic_firmware",
                IMAGE_NAME,
                "pio", "run", "-e", "native_virtual",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        for raw in proc.stdout:
            self._log_line.emit(raw.decode("utf-8", errors="replace").rstrip())

        proc.wait()
        if proc.returncode == 0:
            self._log_line.emit("[Build] Meshtastic firmware build successful")
        else:
            self._log_line.emit(f"[Build] Meshtastic firmware build failed (exit={proc.returncode})")
