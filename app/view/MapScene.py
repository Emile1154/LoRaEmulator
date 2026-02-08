from PyQt6.QtWidgets import (
    QGraphicsScene, QMenu
)
from PyQt6.QtGui import QTransform
class MapScene(QGraphicsScene):
    def __init__(self, node_controller):
        super().__init__()
        self.node_controller = node_controller

    def contextMenuEvent(self, event):
        super().contextMenuEvent(event)
        if self.itemAt(event.scenePos(), QTransform()):
            return

        menu = QMenu()
        act_create = menu.addAction("Create node")

        if menu.exec(event.screenPos()) == act_create:
            pos = event.scenePos()
            self.node_controller.create_node(pos.x(), pos.y(), None)
