import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QPlainTextEdit, QMessageBox

from model.Project import ProjectModel


BINARY_REL = os.path.join("LoRaSDR", "target", "debug", "channel_process")
SPECTRUM_BIN_REL = os.path.join("LoRaSDR", "target", "debug", "spectrum_viewer")
_WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BINARY_PATH = os.path.join(_WORKSPACE, BINARY_REL)
SPECTRUM_BIN_PATH = os.path.join(_WORKSPACE, SPECTRUM_BIN_REL)
_LORASDR_PATH = os.path.join(_WORKSPACE, "LoRaSDR")


class EmulationController(QObject):
    _log_line             = pyqtSignal(str)
    _build_log_line       = pyqtSignal(str)
    _build_done           = pyqtSignal(bool)            # True = success
    _show_rust_alert      = pyqtSignal()
    _spectrum_build_done  = pyqtSignal(bool, int, str)  # success, ws-port, title

    def __init__(self, project_model: ProjectModel,
                 console: QPlainTextEdit | None = None,
                 build_console: QPlainTextEdit | None = None):
        super().__init__()
        self.project = project_model
        self.running = False
        self._process: subprocess.Popen | None = None
        self._tmp_path: str | None = None
        self._console = console
        self._build_console = build_console
        # local_port -> WebSocket spectrum port, parsed from channel_process stdout
        self._spectrum_ports: dict[int, int] = {}
        # keep references to spawned viewer windows so they aren't reaped early
        self._spectrum_viewers: list[subprocess.Popen] = []
        # UDP control port for live node-position updates (parsed from stdout)
        self._control_port: int | None = None
        self._ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._log_line.connect(self._append_log)
        self._build_log_line.connect(self._append_build_log)
        self._build_done.connect(self._on_build_done)
        self._show_rust_alert.connect(self._alert_install_rust)
        self._spectrum_build_done.connect(self._on_spectrum_build_done)

    def _append_log(self, line: str):
        if self._console is None:
            return
        self._console.appendPlainText(line)
        sb = self._console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _append_build_log(self, line: str):
        target = self._build_console if self._build_console is not None else self._console
        if target is None:
            return
        target.appendPlainText(line)
        sb = target.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _read_stdout(self):
        """Background thread: streams Rust process stdout to the console."""
        try:
            for raw in self._process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                self._maybe_capture_spectrum_port(line)
                self._maybe_capture_control_port(line)
                self._log_line.emit(line)
        except Exception:
            pass

    def _maybe_capture_spectrum_port(self, line: str):
        """Parse 'SPECTRUM node=I local_port=L port=P' lines emitted by
        channel_process and remember which WebSocket port feeds each node."""
        if not line.startswith("SPECTRUM "):
            return
        fields = {}
        for tok in line.split()[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                fields[k] = v
        try:
            local_port = int(fields["local_port"])
            port = int(fields["port"])
        except (KeyError, ValueError):
            return
        self._spectrum_ports[local_port] = port

    def _maybe_capture_control_port(self, line: str):
        """Parse the 'CONTROL port=P' line that channel_process emits for the
        live node-position UDP endpoint."""
        if not line.startswith("CONTROL "):
            return
        for tok in line.split()[1:]:
            if tok.startswith("port="):
                try:
                    self._control_port = int(tok.split("=", 1)[1])
                except ValueError:
                    pass

    def send_position(self, local_port: int, x: float, y: float):
        """Push a node's new position to the running channel so path-loss
        updates live. No-op if emulation isn't running yet."""
        if not self.running or self._control_port is None:
            return
        msg = json.dumps({"local_port": int(local_port), "x": float(x), "y": float(y)})
        try:
            self._ctrl_sock.sendto(msg.encode("utf-8"), ("127.0.0.1", self._control_port))
        except OSError as e:
            self._log_line.emit(f"[Control] position send failed: {e}")

    def show_spectrum(self, node_model):
        """Open a live spectrum window for the given node (right-click action)."""
        if not self.running:
            self._log_line.emit("[Spectrum] Emulation is not running")
            return
        port = self._spectrum_ports.get(node_model.local_port)
        if port is None:
            self._log_line.emit(
                f"[Spectrum] No spectrum feed for node {node_model.short_mac()} "
                f"(local_port={node_model.local_port})"
            )
            return
        title = node_model.short_mac()
        if not os.path.isfile(SPECTRUM_BIN_PATH):
            if shutil.which("cargo") is None:
                self._show_rust_alert.emit()
                return
            self._log_line.emit(
                "[Spectrum] spectrum_viewer binary not found — building..."
            )
            threading.Thread(
                target=self._build_spectrum,
                args=(port, title),
                daemon=True,
                name="spectrum_build",
            ).start()
            return
        self._launch_spectrum(port, title)

    def _launch_spectrum(self, port: int, title: str):
        if not os.path.isfile(SPECTRUM_BIN_PATH):
            self._log_line.emit("[Spectrum] viewer binary still missing after build")
            return
        try:
            proc = subprocess.Popen(
                [SPECTRUM_BIN_PATH, "--port", str(port), "--title", title],
            )
            self._spectrum_viewers.append(proc)
            self._log_line.emit(f"[Spectrum] Opened spectrum for {title} on ws:{port}")
        except Exception as e:
            self._log_line.emit(f"[Spectrum] Failed to launch viewer: {e}")

    def _build_spectrum(self, port: int, title: str):
        """Background thread: cargo build spectrum_viewer, then launch it."""
        self._build_log_line.emit(
            "[Build] Building spectrum_viewer (this may take a minute)..."
        )
        proc = subprocess.Popen(
            ["cargo", "build", "--bin", "spectrum_viewer"],
            cwd=_LORASDR_PATH,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        for raw in proc.stdout:
            self._build_log_line.emit(raw.decode("utf-8", errors="replace").rstrip())
        proc.wait()
        ok = proc.returncode == 0
        if ok:
            self._build_log_line.emit("[Build] spectrum_viewer build successful")
        else:
            self._build_log_line.emit(
                f"[Build] spectrum_viewer build failed (exit={proc.returncode})"
            )
        self._spectrum_build_done.emit(ok, port, title)

    def _on_spectrum_build_done(self, success: bool, port: int, title: str):
        if not success:
            self._log_line.emit("[Spectrum] viewer build failed — see Build console")
            return
        if not self.running:
            self._log_line.emit("[Spectrum] Emulation stopped before viewer was ready")
            return
        self._launch_spectrum(port, title)

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
        self._build_log_line.emit("[Build] Building channel_process (this may take a minute)...")
        proc = subprocess.Popen(
            ["cargo", "build", "--bin", "channel_process"],
            cwd=_LORASDR_PATH,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        for raw in proc.stdout:
            self._build_log_line.emit(raw.decode("utf-8", errors="replace").rstrip())
        proc.wait()
        if proc.returncode == 0:
            self._build_log_line.emit("[Build] channel_process build successful")
            self._build_done.emit(True)
        else:
            self._build_log_line.emit(f"[Build] channel_process build failed (exit={proc.returncode})")
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

        self._spectrum_ports.clear()
        self._control_port = None

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

        # Close any open spectrum windows — their WebSocket feeds are now gone.
        for proc in self._spectrum_viewers:
            if proc.poll() is None:
                proc.terminate()
        self._spectrum_viewers.clear()
        self._spectrum_ports.clear()
        self._control_port = None

        self.running = False
        self._log_line.emit("[EmulationController] Emulation stopped")
