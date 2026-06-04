import os
from controller.NodeController import NodeController
from model.Project import ProjectModel
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QGraphicsScene, QFileDialog
from view.NodeItem import NodeItem

_SETTINGS_ORG  = "LoRaEmulator"
_SETTINGS_APP  = "LoRaEmulator"
_RECENT_KEY    = "recentFiles"
_RECENT_MAX    = 8


class ProjectController:
    def __init__(self, model: ProjectModel, node_controller: NodeController, scene: QGraphicsScene):
        self.model = model
        self.node_controller = node_controller
        self.scene = scene

    # ── recent files ──────────────────────────────────────────────────────────

    @staticmethod
    def get_recent() -> list[str]:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        return [p for p in (s.value(_RECENT_KEY) or []) if os.path.isfile(p)]

    @staticmethod
    def _add_recent(path: str):
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        files: list = list(s.value(_RECENT_KEY) or [])
        if path in files:
            files.remove(path)
        files.insert(0, path)
        s.setValue(_RECENT_KEY, files[:_RECENT_MAX])

    # ── project I/O ───────────────────────────────────────────────────────────

    def new_project(self):
        self.model.clear()
        self.scene.clear()

    def save_project(self, parent):
        if self.model.file_path is None:
            path, _ = QFileDialog.getSaveFileName(parent, "Save project", "project.json", "JSON (*.json)")
            if not path:
                return
            self.model.file_path = path

        with open(self.model.file_path, "w") as f:
            f.write(self.model.to_json())
        self._add_recent(self.model.file_path)

    def open_project(self, parent):
        path, _ = QFileDialog.getOpenFileName(parent, "Open project", "", "JSON (*.json)")
        if path:
            self._load_file(path)

    def open_recent(self, path: str):
        self._load_file(path)

    def _load_file(self, path: str):
        with open(path) as f:
            self.model.from_json(f.read())
        self.model.file_path = path
        self.scene.clear()
        self.model.gui_nodes.clear()
        for node in self.model.nodes:
            item = NodeItem(node, self.node_controller)
            self.node_controller.register_node(item)
            self.model.gui_nodes.append(item)
            self.scene.addItem(item)
        self._add_recent(path)
