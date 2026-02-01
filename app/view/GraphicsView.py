from PyQt6.QtWidgets import (
    QGraphicsView,
)
from PyQt6.QtGui import QPen, QPainter, QKeySequence
from PyQt6.QtCore import Qt, pyqtSignal, QPoint

GRID_SIZE = 40
ZOOM_FACTOR = 1.15

class GraphicsView(QGraphicsView):
    mouseMoved = pyqtSignal(float, float)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._panning = False
        self._pan_start = QPoint()

    def drawBackground(self, painter, rect):
        painter.setPen(QPen(Qt.GlobalColor.lightGray))
        left = int(rect.left()) - (int(rect.left()) % GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % GRID_SIZE)
        right = int(rect.right())
        bottom = int(rect.bottom())

        x = left
        while x <= right:
            painter.drawLine(x, top, x, bottom)
            x += GRID_SIZE

        y = top
        while y <= bottom:
            painter.drawLine(left, y, right, y)
            y += GRID_SIZE

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = ZOOM_FACTOR if event.angleDelta().y() > 0 else 1 / ZOOM_FACTOR
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal)):
            self.scale(ZOOM_FACTOR, ZOOM_FACTOR)
            event.accept()
            return
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.key() == Qt.Key.Key_Minus):
            self.scale(1 / ZOOM_FACTOR, 1 / ZOOM_FACTOR)
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.ZoomIn):
            self.scale(ZOOM_FACTOR, ZOOM_FACTOR)
        elif event.matches(QKeySequence.StandardKey.ZoomOut):
            self.scale(1 / ZOOM_FACTOR, 1 / ZOOM_FACTOR)
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        p = self.mapToScene(event.pos())
        self.mouseMoved.emit(p.x(), p.y())
        
        if self._panning:
            if event.modifiers():
                delta = event.pos() - self._pan_start
                self._pan_start = event.pos()
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
                event.accept()
                return 
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
