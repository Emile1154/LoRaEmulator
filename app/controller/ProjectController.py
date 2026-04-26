from controller.NodeController import NodeController
from model.Project import ProjectModel
from PyQt6.QtWidgets import QGraphicsScene, QFileDialog
from view.NodeItem import NodeItem

class ProjectController:
    def __init__(self, model: ProjectModel, node_controller: NodeController, scene: QGraphicsScene):
        self.model = model
        self.node_controller = node_controller
        self.scene = scene

    def new_project(self):
        self.model.clear()
        self.scene.clear()

    def save_project(self, parent):
        # If no file path set (first save), show dialog
        if self.model.file_path is None:
            path, _ = QFileDialog.getSaveFileName(parent, "Save project", "project.json", "JSON (*.json)")
            if not path:
                return  # User cancelled
            self.model.file_path = path
        
        # Save to the stored file path
        with open(self.model.file_path, "w") as f:
            f.write(self.model.to_json())

    def open_project(self, parent):
        path, _ = QFileDialog.getOpenFileName(parent, "Open project", "", "JSON (*.json)")
        if path:
            with open(path) as f:
                self.model.from_json(f.read())
            self.model.file_path = path
            self.scene.clear()
            self.model.gui_nodes.clear()
            for node in self.model.nodes:
                item = NodeItem(node, self.node_controller)
                self.model.gui_nodes.append(item)
                self.scene.addItem(item)
