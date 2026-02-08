from PyQt6.QtWidgets import (
    QGraphicsEllipseItem, QMenu, QGraphicsTextItem
)
from PyQt6.QtGui import QPen, QContextMenuEvent, QBrush, QFont
from PyQt6.QtCore import Qt
from model.Node import Node, State

NODE_RADIUS = 25
STATUS_RADIUS = 4
LABEL_OFFSET_Y = NODE_RADIUS + 6

color_status_dict = {
    State.CREATED  : Qt.GlobalColor.gray,
    State.STARTING : Qt.GlobalColor.yellow,
    State.RUNNING  : Qt.GlobalColor.green,
    State.STOPPED  : Qt.GlobalColor.blue,
    State.ERROR    : Qt.GlobalColor.red,
}
status_text = {
    State.CREATED:  "CREATED",
    State.STARTING:"STARTING",
    State.RUNNING: "RUNNING",
    State.STOPPED: "STOPPED",
    State.ERROR:   "ERROR",
}

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
        self.setAcceptedMouseButtons(Qt.MouseButton.AllButtons)
        self.setPos(model.x, model.y)

        self.name_label = QGraphicsTextItem("TEST1", self)
        self.name_label.setDefaultTextColor(Qt.GlobalColor.black)

        font = QFont()
        font.setPointSize(9)
        self.name_label.setFont(font)

        # --- status text ---
        self.status_label = QGraphicsTextItem("", self)
        self.status_label.setFont(font)

        # --- status indicator ---
        self.status_item = QGraphicsEllipseItem(
            -STATUS_RADIUS, -STATUS_RADIUS,
            STATUS_RADIUS * 2, STATUS_RADIUS * 2,
            self
        )

        self._layout_labels()
        self.setStatus(State.CREATED)
    
    def setStatus(self, state : State):
        color = color_status_dict[state]
        text = status_text[state]

        self.status_label.setPlainText(text)
        self.status_label.setDefaultTextColor(color)

        self.status_item.setBrush(QBrush(color)) 
        self.status_item.setPen(QPen(Qt.PenStyle.NoPen))

        self._layout_labels()

    def _layout_labels(self):
        name_rect = self.name_label.boundingRect()
        status_rect = self.status_label.boundingRect()

        total_width = (
            name_rect.width() +
            6 +
            status_rect.width() +
            6 +
            STATUS_RADIUS * 2
        )

        y = LABEL_OFFSET_Y

        x = -total_width / 2

        self.name_label.setPos(x, y)
        x += name_rect.width() + 6

        self.status_label.setPos(x, y)
        x += status_rect.width() + 6

        self.status_item.setPos(
            x + STATUS_RADIUS,
            y + status_rect.height() / 2
        )

    def mouseReleaseEvent(self, event):
        self.controller.update_position(self, self.pos())
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.controller.edit_node(self)
            event.accept()
        else:
            event.ignore()

    def contextMenuEvent(self, event):
        event.accept()

        menu = QMenu()

        act_edit = menu.addAction("Edit")
        act_delete = menu.addAction("Delete")

        menu.addSeparator()

        act_enable = menu.addAction("Enable Device")
        act_disable = menu.addAction("Disable Device")

        menu.addSeparator()

        act_web = menu.addAction("Open web interface")
        act_term = menu.addAction("Open terminal")

        # --- state logic ---
        is_running = self.model.state == State.RUNNING

        act_enable.setEnabled(not is_running)
        act_disable.setEnabled(is_running)

        act_web.setEnabled(is_running)
        act_term.setEnabled(is_running)

        # --- execute ---
        action = menu.exec(event.screenPos())

        if action == act_edit:
            self.controller.edit_node(self)

        elif action == act_delete:
            self.controller.delete_node(self)

        elif action == act_enable:
            self.controller.enable_node(self)

        elif action == act_disable:
            self.controller.disable_node(self)

        elif action == act_web:
            self.controller.open_web(self)

        elif action == act_term:
            self.controller.open_terminal(self)
