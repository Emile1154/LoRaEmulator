
from model.Project import ProjectModel
from PyQt6.QtWidgets import QGraphicsScene, QFileDialog
from model.Node import Node
from view.NodeItem import NodeItem
from view.dialogs import NodeDialog

class NodeController:
    def __init__(self, project_model: ProjectModel, scene: QGraphicsScene):
        self.project = project_model
        self.scene = scene

    def create_node(self, x, y, parent):
        model = Node(8000, 1000, 2000, x, y)
        dlg = NodeDialog(model, parent)
        if dlg.exec():
            dlg.apply()
            self.project.nodes.append(model)
            self.scene.addItem(NodeItem(model, self))

    def edit_node(self, item: NodeItem):
        dlg = NodeDialog(item.model)
        if dlg.exec():
            dlg.apply()
            item.setPos(item.model.x, item.model.y)

    def delete_node(self, item: NodeItem):
        self.project.nodes.remove(item.model)
        self.scene.removeItem(item)

    def update_position(self, item: NodeItem, pos):
        item.model.x = pos.x()
        item.model.y = pos.y()

    def open_web(self, item: NodeItem):
        print(f"Open web interface on port {item.model.web_port}")

    def open_terminal(self, item: NodeItem):
        print(f"Open terminal for node {item.model.local_port}")