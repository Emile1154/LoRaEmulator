from typing import Callable

from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QBrush
from PyQt6.QtCore import Qt, QTimer, QPointF


class PacketArrow:
    """
    Animated dashed arrow with a travelling dot from src to dst.
    Line width and dot size are zoom-independent (cosmetic pen + ItemIgnoresTransformations).

    Roles:
      * "data" : provisional origin->dest arrow. Stays orange until confirmed
                 (turns blue) or times out (turns red + "Packet Missed").
      * "hop"  : a single data relay hop. Auto-turns blue when the dot arrives.
      * "ack"  : an acknowledgement hop. Auto-turns violet when it arrives.
    """
    _STEP_MS  = 30
    _DURATION = 1100

    # Color states
    COLOR_PENDING = QColor(255, 160, 0)    # Orange - in flight / waiting
    COLOR_SUCCESS = QColor(60, 180, 255)   # Blue   - delivered / acked
    COLOR_TIMEOUT = QColor(255, 60, 60)    # Red    - timeout, lost
    COLOR_RELAY   = QColor(0, 200, 120)    # Green  - relay hop confirmed
    COLOR_ACK     = QColor(180, 120, 255)  # Violet - acknowledgement confirmed

    def __init__(self, scene, src: QPointF, dst: QPointF,
                 role: str = "data",
                 on_done: Callable | None = None,
                 on_missed: Callable | None = None,
                 timeout_ms: int = 5000):
        self._scene = scene
        self._src = src
        self._dst = dst
        self._p = 0.0
        self._role = role
        self._on_done = on_done
        self._on_missed = on_missed
        self._color = self.COLOR_PENDING
        self._state = "pending"  # pending, success, timeout
        self._delivered = False
        self._auto_success = role in ("hop", "ack")

        width = 2 if role == "data" else 1
        line_pen = QPen(QColor(self._color.red(), self._color.green(),
                               self._color.blue(), 160), width, Qt.PenStyle.DashLine)
        line_pen.setCosmetic(True)  # constant width regardless of zoom
        self._width = width

        self._line = QGraphicsLineItem(src.x(), src.y(), dst.x(), dst.y())
        self._line.setPen(line_pen)
        self._line.setZValue(9)
        scene.addItem(self._line)

        self._dot = QGraphicsEllipseItem(-5, -5, 10, 10)
        self._dot.setBrush(QBrush(self._color))
        self._dot.setPen(QPen(Qt.PenStyle.NoPen))
        self._dot.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self._dot.setPos(src)
        self._dot.setZValue(10)
        scene.addItem(self._dot)

        self._timer = QTimer()
        self._timer.setInterval(self._STEP_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # Timeout only matters for the end-to-end delivery arrow.
        self._timeout_timer = QTimer()
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.setInterval(timeout_ms)
        self._timeout_timer.timeout.connect(self._on_timeout)
        if role == "data":
            self._timeout_timer.start()

    def _tick(self):
        self._p += self._STEP_MS / self._DURATION
        if self._p >= 1.0:
            self._dot.setVisible(False)
            # Hops are confirmed the moment they arrive.
            if self._auto_success and self._state == "pending":
                self.set_state("ack" if self._role == "ack" else "success")
            return
        t = self._p
        self._dot.setPos(
            self._src.x() + (self._dst.x() - self._src.x()) * t,
            self._src.y() + (self._dst.y() - self._src.y()) * t,
        )
        alpha = int(160 * (1.0 - t * 0.6))
        pen = QPen(QColor(self._color.red(), self._color.green(),
                          self._color.blue(), alpha), self._width, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self._line.setPen(pen)

    def _on_timeout(self):
        """No confirmation arrived in time -> packet considered lost."""
        if self._state == "pending" and not self._delivered:
            self.set_state("timeout")
            if self._on_missed:
                self._on_missed(self)

    def mark_delivered(self):
        """Data reached the destination but we still wait for the ACK.

        Keeps the arrow orange but cancels the loss timeout.
        """
        self._delivered = True
        self._timeout_timer.stop()

    def set_state(self, state: str):
        """Update arrow state: pending, success, timeout, relay, ack."""
        if state == self._state:
            return
        self._state = state

        if state == "success":
            self._color = self.COLOR_SUCCESS
        elif state == "timeout":
            self._color = self.COLOR_TIMEOUT
        elif state == "relay":
            self._color = self.COLOR_RELAY
        elif state == "ack":
            self._color = self.COLOR_ACK
        else:
            self._color = self.COLOR_PENDING

        pen = QPen(QColor(self._color.red(), self._color.green(),
                          self._color.blue(), 160), self._width, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self._line.setPen(pen)
        self._dot.setBrush(QBrush(self._color))

        if state != "pending":
            self._timeout_timer.stop()
            # Keep the final state on screen briefly, then remove.
            QTimer.singleShot(2000, self._cleanup)

    def _cleanup(self):
        """Remove arrow from scene"""
        self._timer.stop()
        self._timeout_timer.stop()
        if self._line.scene():
            self._scene.removeItem(self._line)
        if self._dot.scene():
            self._scene.removeItem(self._dot)
        if self._on_done:
            self._on_done(self)


class PacketTracker:
    """
    Owns the live arrows and routes monitor commands to them, keyed by a
    stable string id so confirmations match regardless of node positions.
    """
    def __init__(self, scene):
        self._scene = scene
        self._arrows: list[PacketArrow] = []
        self._by_key: dict[str, PacketArrow] = {}
        self._tx_timeout_ms = 20000  # emulator round-trips can take >10 s

    def add(self, action: str, key: str, a_pos: QPointF, b_pos: QPointF,
            on_missed: Callable | None = None) -> PacketArrow:
        """Create a new arrow for a 'data' / 'relay' / 'ack' command."""
        # Replace any stale arrow living under the same key.
        old = self._by_key.pop(key, None)
        if old is not None:
            old._cleanup()

        arrow = PacketArrow(
            self._scene, a_pos, b_pos,
            role=action,
            on_done=self._remove_arrow,
            on_missed=on_missed,
            timeout_ms=self._tx_timeout_ms,
        )
        self._arrows.append(arrow)
        self._by_key[key] = arrow
        return arrow

    def confirm(self, key: str):
        """Turn the keyed delivery arrow blue."""
        arrow = self._by_key.get(key)
        if arrow is not None and arrow._state == "pending":
            arrow.set_state("success")

    def delivered(self, key: str):
        """Mark data delivered (waiting for ACK) — stays orange, no timeout."""
        arrow = self._by_key.get(key)
        if arrow is not None:
            arrow.mark_delivered()

    def cancel(self, key: str):
        """Silently remove a keyed arrow (e.g. the provisional direct arrow
        once the packet turns out to be multi-hop)."""
        arrow = self._by_key.pop(key, None)
        if arrow is not None:
            arrow._cleanup()

    def _remove_arrow(self, arrow: PacketArrow):
        if arrow in self._arrows:
            self._arrows.remove(arrow)
        for k in [k for k, v in self._by_key.items() if v is arrow]:
            del self._by_key[k]

    def clear_all(self):
        for arrow in list(self._arrows):
            arrow._cleanup()
        self._arrows.clear()
        self._by_key.clear()
