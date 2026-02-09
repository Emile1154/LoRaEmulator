from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout,
    QTabWidget, QWidget, QComboBox, QCheckBox
)
from model.Node import Node

class NodeDialog(QDialog):
    def __init__(self, model: Node, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Node settings")
        self.model = model

        # Create tabs
        self.tabs = QTabWidget()

        # General Tab
        self.general_tab = QWidget()
        self.general_layout = QVBoxLayout(self.general_tab)

        # Network Settings
        self.network_form = QFormLayout()
        self.web_port = QLineEdit(str(model.web_port))
        self.local_port = QLineEdit(str(model.local_port))
        self.remote_port = QLineEdit(str(model.remote_port))
        self.network_form.addRow("Web server port", self.web_port)
        self.network_form.addRow("Local port", self.local_port)
        self.network_form.addRow("Remote port", self.remote_port)

        self.general_layout.addLayout(self.network_form)

        # Position Settings
        self.position_form = QFormLayout()
        self.pos_x = QLineEdit(str(int(model.x)))
        self.pos_y = QLineEdit(str(int(model.y)))
        self.position_form.addRow("Position X", self.pos_x)
        self.position_form.addRow("Position Y", self.pos_y)

        self.general_layout.addLayout(self.position_form)

        self.tabs.addTab(self.general_tab, "General")

        # Initial Hardware Tab
        self.hardware_tab = QWidget()
        self.hardware_layout = QVBoxLayout(self.hardware_tab)

        # Low Level Settings
        self.low_level_form = QFormLayout()
        self.frequency = QLineEdit()  # Assuming frequency is an int
        self.spreading_factor = QLineEdit()  # Assuming it's uint8_t as text input
        self.bandwidth = QComboBox()  # Dropdown for bandwidth
        self.code_rate = QComboBox()  # Dropdown for code rate
        self.ldro_enable = QCheckBox("LDRO Enable")

        # Populate bandwidth and code_rate dropdowns
        self.bandwidth.addItems(["Low", "Medium", "High"])  # Add suitable options
        self.code_rate.addItems(["1/2", "3/4", "4/5"])  # Add suitable options

        self.low_level_form.addRow("Frequency", self.frequency)
        self.low_level_form.addRow("Spreading Factor", self.spreading_factor)
        self.low_level_form.addRow("Bandwidth", self.bandwidth)
        self.low_level_form.addRow("Code Rate", self.code_rate)
        self.low_level_form.addRow("LDRO Enable", self.ldro_enable)

        self.hardware_layout.addLayout(self.low_level_form)

        # Meshtastic Config
        self.meshtastic_config_button = QPushButton("Meshtastic Config")
        self.hardware_layout.addWidget(self.meshtastic_config_button)

        self.tabs.addTab(self.hardware_tab, "Initial Hardware")

        # Final Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        # OK Button
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

    def apply(self):
        self.model.web_port = int(self.web_port.text())
        self.model.local_port = int(self.local_port.text())
        self.model.remote_port = int(self.remote_port.text())
        self.model.x = float(self.pos_x.text())
        self.model.y = float(self.pos_y.text())
        # Add logic to retrieve values from new hardware fields as necessary
        self.model.frequency = int(self.frequency.text())
        self.model.spreading_factor = int(self.spreading_factor.text())
        self.model.bandwidth = self.bandwidth.currentText()
        self.model.code_rate = self.code_rate.currentText()
        self.model.ldro_enable = self.ldro_enable.isChecked()
