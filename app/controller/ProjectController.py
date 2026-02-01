from controller.NodeController import NodeController
from model.Project import ProjectModel
from PyQt6.QtWidgets import QGraphicsScene, QFileDialog
from model.Node import Node

class ProjectController:
    def __init__(self, model: ProjectModel, node_controller: NodeController, scene: QGraphicsScene):
        self.model = model
        self.node_controller = node_controller
        self.scene = scene

    def new_project(self):
        self.model.clear()
        self.scene.clear()

    def save_project(self, parent):
        path, _ = QFileDialog.getSaveFileName(parent, "Save project", "", "JSON (*.json)")
        if path:
            with open(path, "w") as f:
                f.write(self.model.to_json())

    def open_project(self, parent):
        path, _ = QFileDialog.getOpenFileName(parent, "Open project", "", "JSON (*.json)")
        if path:
            with open(path) as f:
                self.model.from_json(f.read())
            self.scene.clear()
            for node in self.model.nodes:
                self.scene.addItem(Node(node, self.node_controller))
