from PyQt6.QtWidgets import (
    QGraphicsEllipseItem, QMenu,
)
from PyQt6.QtGui import QPen 
from PyQt6.QtCore import Qt
from model.Node import Node
NODE_RADIUS = 12
class NodeItem(QGraphicsEllipseItem):
    def __init__(self, model: Node, controller):
        super().__init__(-NODE_RADIUS, -NODE_RADIUS,
                         NODE_RADIUS * 2, NODE_RADIUS * 2)
        self.model = model
        self.controller = controller
        self.setBrush(Qt.GlobalColor.cyan)
        self.setPen(QPen(Qt.GlobalColor.black, 2))
        self.setFlags(
            QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setPos(model.x, model.y)

    def mouseReleaseEvent(self, event):
        self.controller.update_position(self, self.pos())
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.controller.edit_node(self)

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_edit = menu.addAction("Edit")
        act_delete = menu.addAction("Delete")
        menu.addSeparator()
        act_web = menu.addAction("Open web interface")
        act_term = menu.addAction("Open terminal")

        action = menu.exec(event.screenPos())
        if action == act_edit:
            self.controller.edit_node(self)
        elif action == act_delete:
            self.controller.delete_node(self)
        elif action == act_web:
            self.controller.open_web(self)
        elif action == act_term:
            self.controller.open_terminal(self)
