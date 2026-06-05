from PyQt6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsItem, QMenu, QGraphicsTextItem,
    QApplication, QGraphicsRectItem
)
from PyQt6.QtGui import QPen, QContextMenuEvent, QBrush, QFont, QColor
from PyQt6.QtCore import Qt, QTimer, QRectF
from model.Node import Node, State, status_text
NODE_RADIUS = 25
STATUS_RADIUS = 4
LABEL_OFFSET_Y = NODE_RADIUS + 6
_RX_OVERLAY_Y = LABEL_OFFSET_Y + 22   # below the status labels
_TX_OVERLAY_Y = -(NODE_RADIUS + 80)   # above the node

color_status_dict = {
    State.CREATED  : Qt.GlobalColor.gray,
    State.STARTING : Qt.GlobalColor.darkYellow,
    State.RUNNING  : Qt.GlobalColor.darkGreen,
    State.STOPPED  : Qt.GlobalColor.blue,
    State.STOPPING : Qt.GlobalColor.darkYellow,
    State.ERROR    : Qt.GlobalColor.red,
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
            QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
        )
        self.setAcceptedMouseButtons(Qt.MouseButton.AllButtons)
        self.setPos(model.x, model.y)

        # --- background for labels ---
        self.label_bg = QGraphicsRectItem(self)
        self.label_bg.setBrush(QBrush(Qt.GlobalColor.white))
        self.label_bg.setPen(QPen(Qt.GlobalColor.black, 1))
        self.label_bg.setZValue(-1)  # Behind text labels

        self.name_label = QGraphicsTextItem(self)
        self.name_label.setDefaultTextColor(Qt.GlobalColor.black)
        self.name_label.setPlainText(model.short_mac())

        font = QFont()
        font.setPointSize(9)
        self.name_label.setFont(font)

        # --- status text ---
        self.status_label = QGraphicsTextItem(self)
        self.status_label.setFont(font)

        # --- status indicator ---
        self.status_item = QGraphicsEllipseItem(
            -STATUS_RADIUS, -STATUS_RADIUS,
            STATUS_RADIUS * 2, STATUS_RADIUS * 2,
            self
        )

        # Spinner animation (shown while state is STARTING / STOPPING)
        self._spin_angle = 0
        self._spin_timer = QTimer()
        self._spin_timer.setInterval(40)   # ~25 fps
        self._spin_timer.timeout.connect(self._tick_spinner)

        self.setStatus(model.state)

        self._layout_labels()

        overlay_font = QFont("Monospace", 8)

        # RX overlay — below node
        self._rx_bg = QGraphicsRectItem(self)
        self._rx_bg.setBrush(QBrush(QColor(0, 0, 0, 170)))
        self._rx_bg.setPen(QPen(QColor(80, 160, 255, 180), 1))
        self._rx_bg.setZValue(2)
        self._rx_bg.setVisible(False)

        self._rx_label = QGraphicsTextItem(self)
        self._rx_label.setFont(overlay_font)
        self._rx_label.setDefaultTextColor(QColor(60, 180, 255))
        self._rx_label.setZValue(3)
        self._rx_label.setVisible(False)

        self._rx_hide_timer = QTimer()
        self._rx_hide_timer.setSingleShot(True)
        self._rx_hide_timer.setInterval(5000)
        self._rx_hide_timer.timeout.connect(self._hide_rx_overlay)

        # TX overlay — above node
        self._tx_bg = QGraphicsRectItem(self)
        self._tx_bg.setBrush(QBrush(QColor(0, 0, 0, 170)))
        self._tx_bg.setPen(QPen(QColor(255, 160, 0, 180), 1))
        self._tx_bg.setZValue(2)
        self._tx_bg.setVisible(False)

        self._tx_label = QGraphicsTextItem(self)
        self._tx_label.setFont(overlay_font)
        self._tx_label.setDefaultTextColor(QColor(255, 160, 0))
        self._tx_label.setZValue(3)
        self._tx_label.setVisible(False)

        self._tx_hide_timer = QTimer()
        self._tx_hide_timer.setSingleShot(True)
        self._tx_hide_timer.setInterval(5000)
        self._tx_hide_timer.timeout.connect(self._hide_tx_overlay)
    
    def _tick_spinner(self):
        self._spin_angle = (self._spin_angle - 12) % 360  # counter-clockwise, 12°/tick
        self.update()

    def setStatus(self, state: State):
        color = color_status_dict[state]
        text = status_text[state]

        self.status_label.setPlainText(text)
        self.status_label.setDefaultTextColor(color)

        self.status_item.setBrush(QBrush(color))
        self.status_item.setPen(QPen(Qt.PenStyle.NoPen))

        self.model.state = state

        # Spinner: run while the node is in a transient state
        if state in (State.STARTING, State.STOPPING):
            if not self._spin_timer.isActive():
                self._spin_timer.start()
        else:
            self._spin_timer.stop()
            self.update()  # repaint once to clear any leftover arc

        self._layout_labels()

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self._spin_timer.isActive():
            r = NODE_RADIUS - 10
            pen = QPen(QColor(255, 255, 255, 200), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                QRectF(-r, -r, r * 2, r * 2),
                self._spin_angle * 16,   # start angle  (Qt: 1/16 deg)
                270 * 16,                # span: 270° arc
            )

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

        # Update background rectangle to cover both labels
        bg_x = -total_width / 2 - 3
        bg_y = y - 2
        bg_width = name_rect.width() + status_rect.width() + 12 + 3
        bg_height = max(name_rect.height(), status_rect.height()) + 4
        self.label_bg.setRect(bg_x, bg_y, bg_width, bg_height)

    def show_rx_result(self, snr: float, rssi: float,
                       msg_str: str = "", raw_data: bytes = b"",
                       want_response: bool = False):
        self.show_packet_info("RX", snr, rssi, msg_str, raw_data, want_response)

    def show_packet_info(self, direction: str, snr: float, rssi: float,
                         msg_str: str = "", raw_data: bytes = b"",
                         want_response: bool = False):
        import math
        is_tx = direction == "TX"
        lines = [direction]
        if msg_str:
            lines.append(msg_str[:48] + ("…" if len(msg_str) > 48 else ""))
        if raw_data:
            hex_s = raw_data[:8].hex(" ") + (" …" if len(raw_data) > 8 else "")
            lines.append(f"raw:  {hex_s}")
        lines.append(f"ack:  {want_response}")
        if not is_tx:
            snr_str  = f"{snr:+.1f} dB"  if (snr  != 0.0 and not math.isinf(snr))  else "N/A"
            rssi_str = f"{rssi:.0f} dBm" if (rssi != 0.0 and not math.isinf(rssi)) else "N/A"
            lines.append(f"SNR  {snr_str}")
            lines.append(f"RSSI {rssi_str}")
        text = "\n".join(lines)

        if is_tx:
            label, bg, timer, overlay_y = self._tx_label, self._tx_bg, self._tx_hide_timer, _TX_OVERLAY_Y
        else:
            label, bg, timer, overlay_y = self._rx_label, self._rx_bg, self._rx_hide_timer, _RX_OVERLAY_Y

        label.setPlainText(text)
        r = label.boundingRect()
        margin = 4
        label.setPos(-r.width() / 2, overlay_y)
        bg.setRect(
            -r.width() / 2 - margin, overlay_y - margin,
            r.width() + margin * 2, r.height() + margin * 2,
        )
        label.setVisible(True)
        bg.setVisible(True)
        timer.start()

    def _hide_rx_overlay(self):
        self._rx_label.setVisible(False)
        self._rx_bg.setVisible(False)

    def _hide_tx_overlay(self):
        self._tx_label.setVisible(False)
        self._tx_bg.setVisible(False)

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
        act_setup_term = menu.addAction("Open setup terminal")
        act_view_rx = menu.addAction("View received packets")

        # API connect/disconnect + ping + send message — meshtastic only
        act_api_connect = act_api_disconnect = None
        act_pings = []      # [(QAction, target NodeItem)]
        act_messages = []   # [(QAction, target NodeItem)]
        if self.model.network_type == "meshtastic":
            menu.addSeparator()
            act_api_connect = menu.addAction("Connect Python API client")
            act_api_disconnect = menu.addAction("Disconnect Python API client")

            ping_menu = menu.addMenu("Send ping to...")
            msg_menu  = menu.addMenu("Send message to...")
            for other in self.controller.project.gui_nodes:
                if other is self:
                    continue
                if other.model.state == State.RUNNING:
                    label = f"{other.model.short_mac()}  (:{other.model.local_port})"
                    act_pings.append((ping_menu.addAction(label), other))
                    act_messages.append((msg_menu.addAction(label), other))
            if not act_pings:
                ping_menu.setEnabled(False)
            if not act_messages:
                msg_menu.setEnabled(False)

        # --- state logic ---
        is_running = self.model.state == State.RUNNING
        api_connected = self.model.interface is not None

        act_enable.setEnabled(not is_running)
        act_disable.setEnabled(True)

        act_web.setEnabled(is_running)
        act_term.setEnabled(is_running)
        act_view_rx.setEnabled(True)

        if act_api_connect is not None:
            act_api_connect.setEnabled(is_running and not api_connected)
            act_api_disconnect.setEnabled(is_running and api_connected)
            for act, _ in act_pings:
                act.setEnabled(api_connected)
            for act, _ in act_messages:
                act.setEnabled(api_connected)

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
            self.controller.open_terminal(self, False)

        elif action == act_setup_term:
            self.controller.open_terminal(self, True)

        elif action == act_view_rx:
            self.controller.show_received(self)

        elif act_api_connect is not None and action == act_api_connect:
            self.controller.connect_api_client(self)

        elif act_api_disconnect is not None and action == act_api_disconnect:
            self.controller.disconnect_api_client(self)

        else:
            for act_ping, target_item in act_pings:
                if action == act_ping:
                    self.controller.send_ping(self, target_item)
                    break
            for act_msg, target_item in act_messages:
                if action == act_msg:
                    self.controller.send_message_dialog(self, target_item)
                    break
