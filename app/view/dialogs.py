from PyQt6.QtWidgets import (
    QDialog, QFormLayout,
    QLineEdit, QPushButton, QVBoxLayout, 
)
from model.Node import Node
class NodeDialog(QDialog):
    def __init__(self, model: Node, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Node settings")
        self.model = model

        self.web_port = QLineEdit(str(model.web_port))
        self.local_port = QLineEdit(str(model.local_port))
        self.remote_port = QLineEdit(str(model.remote_port))
        self.pos_x = QLineEdit(str(int(model.x)))
        self.pos_y = QLineEdit(str(int(model.y)))

        form = QFormLayout()
        form.addRow("Web server port", self.web_port)
        form.addRow("Local port", self.local_port)
        form.addRow("Remote port", self.remote_port)
        form.addRow("Position X", self.pos_x)
        form.addRow("Position Y", self.pos_y)

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btn_ok)

    def apply(self):
        self.model.web_port = int(self.web_port.text())
        self.model.local_port = int(self.local_port.text())
        self.model.remote_port = int(self.remote_port.text())
        self.model.x = float(self.pos_x.text())
        self.model.y = float(self.pos_y.text())
