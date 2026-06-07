import sys

from controller.BuildController import BuildController
from controller.EmulationController import EmulationController
from controller.NodeController import NodeController
from controller.PacketMonitor import PacketMonitor
from controller.ProjectController import ProjectController
from PyQt6.QtWidgets import (
    QApplication, QMainWindow,
    QLabel, QSplitter, QPlainTextEdit, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QKeySequence, QAction
from model.Project import ProjectModel
from view.GraphicsView import GraphicsView
from view.MapScene import MapScene
from view.PacketAnimation import PacketTracker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Node Emulator")
        self.resize(1000, 700)

        self.project_model = ProjectModel()

        self.scene = MapScene(None)
        self.scene.setSceneRect(-5000, -5000, 5000, 5000)
        self.view = GraphicsView(self.scene)

        # Console tabs at the bottom
        self.emulation_console = self._make_console()
        self.node_console = self._make_console()
        self.build_console = self._make_console()

        tab_widget = QTabWidget()
        tab_widget.setDocumentMode(True)
        tab_widget.addTab(self.emulation_console, "Emulation")
        tab_widget.addTab(self.node_console, "Nodes")
        tab_widget.addTab(self.build_console, "Build")
        tab_widget.setMinimumHeight(60)

        # Splitter: map on top, console on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.view)
        splitter.addWidget(tab_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([550, 150])

        self.setCentralWidget(splitter)

        self.node_controller = NodeController(self.project_model, self.scene, self.node_console)
        self.project_controller = ProjectController(self.project_model, self.node_controller, self.scene)
        self.emulation_controller = EmulationController(
            self.project_model, self.emulation_console, self.build_console
        )
        self.build_controller = BuildController(self.build_console)

        self.scene.node_controller = self.node_controller

        self.coord_label = QLabel("X: 0  Y: 0")
        self.statusBar().addPermanentWidget(self.coord_label)
        self.view.mouseMoved.connect(self.update_coords)
        self._create_menu()

        # Packet animation via meshtastic Python API
        self._packet_tracker = PacketTracker(self.scene)
        self.packet_monitor = PacketMonitor(self.project_model)
        self.node_controller.packet_monitor = self.packet_monitor
        self.packet_monitor.overlay_event.connect(self._on_overlay_event)
        self.packet_monitor.arrow_event.connect(self._on_arrow_event)

    def _make_console(self) -> QPlainTextEdit:
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setMaximumBlockCount(2000)
        w.setFont(QFont("Monospace", 9))
        w.setStyleSheet("QPlainTextEdit { background: #1e1e1e; color: #d4d4d4; border: none; }")
        return w

    def update_coords(self, x, y):
        self.coord_label.setText(f"X: {int(x)}  Y: {int(y)}")

    def _create_menu(self):
        menu_file = self.menuBar().addMenu("File")
        menu_file.addAction("New project", self.project_controller.new_project)
        menu_file.addAction("Open project", lambda: self.project_controller.open_project(self))

        self._recent_menu = menu_file.addMenu("Open Recent")
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)

        menu_file.addSeparator()

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(lambda: self.project_controller.save_project(self))
        menu_file.addAction(save_action)

        menu_run = self.menuBar().addMenu("Run")
        menu_run.addAction("Launch All Devices", self.node_controller.launch_all)
        menu_run.addAction("Shutdown All Devices", self.node_controller.shutdown_all)
        menu_run.addAction("Start emulation", self.emulation_controller.start)
        menu_run.addAction("Stop emulation", self.emulation_controller.stop)

        menu_options = self.menuBar().addMenu("Options")
        menu_options.addAction("Rebuild channel emulator", self.emulation_controller.rebuild)
        menu_options.addAction("Rebuild Meshtastic firmware", self.build_controller.rebuild_meshtastic)

        self._goto_menu = menu_options.addMenu("Go to node")
        self._goto_menu.aboutToShow.connect(self._rebuild_goto_menu)

        self.menuBar().addAction("About program")

    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        files = self.project_controller.get_recent()
        if not files:
            self._recent_menu.addAction("(empty)").setEnabled(False)
            return
        for path in files:
            import os
            label = os.path.basename(path)
            action = self._recent_menu.addAction(label)
            action.setToolTip(path)
            action.triggered.connect(lambda *_, p=path: self.project_controller.open_recent(p))

    def _rebuild_goto_menu(self):
        self._goto_menu.clear()
        items = self.project_model.gui_nodes
        if not items:
            self._goto_menu.addAction("(no nodes)").setEnabled(False)
            return
        for item in items:
            label = item.model.short_mac()
            action = self._goto_menu.addAction(label)
            action.triggered.connect(lambda *_, it=item: self.view.centerOn(it.pos()))

    def _on_overlay_event(self, node_idx: int, kind: str, snr: float, rssi: float,
                          msg_str: str, raw_data: object, want_ack: bool):
        items = self.project_model.gui_nodes
        if not (0 <= node_idx < len(items)):
            return
        raw = raw_data if isinstance(raw_data, bytes) else b""
        items[node_idx].show_packet_info(kind, snr, rssi, msg_str, raw, want_ack)

    def _on_arrow_event(self, action: str, a_idx: int, b_idx: int, key: str,
                        delay_ms: int):
        # Confirmation / delivery commands are matched purely by key.
        if action == "confirm":
            self._packet_tracker.confirm(key)
            return
        if action == "delivered":
            self._packet_tracker.delivered(key)
            return
        if action == "cancel":
            self._packet_tracker.cancel(key)
            return

        # Arrow-creating commands need both endpoints on screen.
        items = self.project_model.gui_nodes
        if not (0 <= a_idx < len(items) and 0 <= b_idx < len(items)) or a_idx == b_idx:
            return

        on_missed = None
        if action == "data":
            def on_missed(_arrow, idx=b_idx):
                its = self.project_model.gui_nodes
                if 0 <= idx < len(its):
                    its[idx].show_packet_info("MISSED", 0.0, 0.0, "", b"", False)

        def _create():
            its = self.project_model.gui_nodes
            if not (0 <= a_idx < len(its) and 0 <= b_idx < len(its)):
                return
            self._packet_tracker.add(action, key, its[a_idx].pos(), its[b_idx].pos(),
                                     on_missed=on_missed)

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _create)
        else:
            _create()

    def closeEvent(self, event):
        self.node_controller.shutdown_all()
        self.emulation_controller.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
