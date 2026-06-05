from typing import Callable

from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QBrush
from PyQt6.QtCore import Qt, QTimer, QPointF


class PacketArrow:
    """
    Animated dashed arrow with a travelling dot from src to dst.
    Line width and dot size are zoom-independent (cosmetic pen + ItemIgnoresTransformations).
    """
    _STEP_MS  = 30
    _DURATION = 1100

    def __init__(self, scene, src: QPointF, dst: QPointF,
                 color: QColor | None = None,
                 on_done: Callable | None = None):
        self._scene = scene
        self._src = src
        self._dst = dst
        self._p = 0.0
        self._on_done = on_done
        self._color = color or QColor(60, 180, 255)

        line_pen = QPen(QColor(self._color.red(), self._color.green(),
                               self._color.blue(), 160), 2, Qt.PenStyle.DashLine)
        line_pen.setCosmetic(True)  # constant width regardless of zoom

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

    def _tick(self):
        self._p += self._STEP_MS / self._DURATION
        if self._p >= 1.0:
            self._timer.stop()
            self._scene.removeItem(self._line)
            self._scene.removeItem(self._dot)
            if self._on_done:
                self._on_done(self)
            return
        t = self._p
        self._dot.setPos(
            self._src.x() + (self._dst.x() - self._src.x()) * t,
            self._src.y() + (self._dst.y() - self._src.y()) * t,
        )
        alpha = int(160 * (1.0 - t * 0.6))
        pen = QPen(QColor(self._color.red(), self._color.green(),
                          self._color.blue(), alpha), 2, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self._line.setPen(pen)
