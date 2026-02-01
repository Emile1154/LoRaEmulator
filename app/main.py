import sys
from controller.EmulationController import EmulationController
from controller.NodeController import NodeController
from controller.ProjectController import ProjectController
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene,
    QMenu, QLabel
)
from PyQt6.QtCore import Qt

from model.Project import ProjectModel
from view.GraphicsView import GraphicsView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Node Emulator")
        self.resize(1000, 700)

        self.project_model = ProjectModel()

        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.view = GraphicsView(self.scene)
        self.setCentralWidget(self.view)

        self.node_controller = NodeController(self.project_model, self.scene)
        self.project_controller = ProjectController(self.project_model, self.node_controller, self.scene)
        self.emulation_controller = EmulationController(self.project_model)

        self.coord_label = QLabel("X: 0  Y: 0")
        self.statusBar().addPermanentWidget(self.coord_label)
        self.view.mouseMoved.connect(self.update_coords)

        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._view_context_menu)

        self._create_menu()

    def update_coords(self, x, y):
        self.coord_label.setText(f"X: {int(x)}  Y: {int(y)}")

    def _view_context_menu(self, pos):
        scene_pos = self.view.mapToScene(pos)
        menu = QMenu()
        act = menu.addAction("Create node")
        if menu.exec(self.view.mapToGlobal(pos)) == act:
            self.node_controller.create_node(scene_pos.x(), scene_pos.y(), self)

    def _create_menu(self):
        menu_file = self.menuBar().addMenu("File")
        menu_file.addAction("New project", self.project_controller.new_project)
        menu_file.addAction("Open project", lambda: self.project_controller.open_project(self))
        menu_file.addAction("Save", lambda: self.project_controller.save_project(self))

        menu_run = self.menuBar().addMenu("Run")
        menu_run.addAction("Start emulation", self.emulation_controller.start)
        menu_run.addAction("Stop emulation", self.emulation_controller.stop)

        self.menuBar().addAction("About program")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
