import json
import os
import shutil
import subprocess
import tempfile
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QPlainTextEdit, QMessageBox

from model.Project import ProjectModel


BINARY_REL = os.path.join("LoRaSDR", "target", "debug", "channel_process")
_WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BINARY_PATH = os.path.join(_WORKSPACE, BINARY_REL)
_LORASDR_PATH = os.path.join(_WORKSPACE, "LoRaSDR")


class EmulationController(QObject):
    _log_line          = pyqtSignal(str)
    _build_done        = pyqtSignal(bool)   # True = success
    _show_rust_alert   = pyqtSignal()

    def __init__(self, project_model: ProjectModel, console: QPlainTextEdit | None = None):
        super().__init__()
        self.project = project_model
        self.running = False
        self._process: subprocess.Popen | None = None
        self._tmp_path: str | None = None
        self._console = console
        self._log_line.connect(self._append_log)
        self._build_done.connect(self._on_build_done)
        self._show_rust_alert.connect(self._alert_install_rust)

    def _append_log(self, line: str):
        if self._console is None:
            return
        self._console.appendPlainText(line)
        sb = self._console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _read_stdout(self):
        """Background thread: streams Rust process stdout to the console."""
        try:
            for raw in self._process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                self._log_line.emit(line)
        except Exception:
            pass

    def _alert_install_rust(self):
        msg = QMessageBox()
        msg.setWindowTitle("Rust not installed")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            "cargo not found — Rust is required to build the emulation engine.\n\n"
            "Install Rust from: https://rustup.rs"
        )
        msg.exec()

    def _on_build_done(self, success: bool):
        if success and not self.running:
            self._do_start()

    def _build_binary(self):
        """Background thread: cargo build, then emit _build_done."""
        self._log_line.emit("[EmulationController] Building channel_process (this may take a minute)...")
        proc = subprocess.Popen(
            ["cargo", "build", "--bin", "channel_process"],
            cwd=_LORASDR_PATH,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        for raw in proc.stdout:
            self._log_line.emit(raw.decode("utf-8", errors="replace").rstrip())
        proc.wait()
        if proc.returncode == 0:
            self._log_line.emit("[EmulationController] Build successful")
            self._build_done.emit(True)
        else:
            self._log_line.emit(f"[EmulationController] Build failed (exit={proc.returncode})")
            self._build_done.emit(False)

    def start(self):
        if self.running:
            return

        if not self.project.nodes:
            self._log_line.emit("[EmulationController] No nodes in project")
            return

        if not os.path.isfile(BINARY_PATH):
            if shutil.which("cargo") is None:
                self._show_rust_alert.emit()
            else:
                threading.Thread(
                    target=self._build_binary,
                    daemon=True,
                    name="cargo_build",
                ).start()
            return

        self._do_start()

    def _do_start(self):
        nodes_data = [
            {
                "local_port":   node.local_port,
                "remote_port":  node.remote_port,
                "x":            node.x,
                "y":            node.y,
                "region":       node.region,
                "modem_preset": node.modem_preset,
                "noise_std":    node.noise_std,
            }
            for node in self.project.nodes
        ]

        fd, self._tmp_path = tempfile.mkstemp(suffix=".json", prefix="channel_nodes_")
        with os.fdopen(fd, "w") as f:
            json.dump(nodes_data, f)

        self._process = subprocess.Popen(
            [BINARY_PATH, self._tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.running = True

        threading.Thread(
            target=self._read_stdout,
            daemon=True,
            name="channel_log_reader",
        ).start()

        self._log_line.emit(
            f"[EmulationController] Started {len(nodes_data)} nodes (pid={self._process.pid})"
        )
        for n in nodes_data:
            self._log_line.emit(
                f"  local={n['local_port']} remote={n['remote_port']} "
                f"region={n['region']} preset={n['modem_preset']}"
            )

    def rebuild(self):
        """Triggered from menu: force-rebuild channel_process binary."""
        if shutil.which("cargo") is None:
            self._show_rust_alert.emit()
            return
        threading.Thread(
            target=self._build_binary,
            daemon=True,
            name="cargo_build",
        ).start()

    def stop(self):
        if not self.running:
            return

        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

        if self._tmp_path and os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)
            self._tmp_path = None

        self.running = False
        self._log_line.emit("[EmulationController] Emulation stopped")
