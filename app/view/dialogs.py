from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout,
    QTabWidget, QWidget, QComboBox, QCheckBox, QRadioButton,
    QButtonGroup, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from model.Node import Node

class NodeDialog(QDialog):
    # Region definitions from freq_calc.ts (freq in MHz)
    REGIONS = {
        "US": {"freq_start": 902.0, "freq_end": 928.0, "duty_cycle": 100, "power_limit": 30},
        "EU_433": {"freq_start": 433.0, "freq_end": 434.0, "duty_cycle": 10, "power_limit": 12},
        "EU_868": {"freq_start": 869.4, "freq_end": 869.65, "duty_cycle": 10, "power_limit": 27},
        "CN": {"freq_start": 470.0, "freq_end": 510.0, "duty_cycle": 100, "power_limit": 19},
        "JP": {"freq_start": 920.8, "freq_end": 927.8, "duty_cycle": 100, "power_limit": 16},
        "ANZ": {"freq_start": 915.0, "freq_end": 928.0, "duty_cycle": 100, "power_limit": 30},
        "ANZ_433": {"freq_start": 433.05, "freq_end": 434.79, "duty_cycle": 100, "power_limit": 14},
        "RU": {"freq_start": 868.7, "freq_end": 869.2, "duty_cycle": 100, "power_limit": 20},
        "KR": {"freq_start": 920.0, "freq_end": 923.0, "duty_cycle": 100, "power_limit": 0},
        "TW": {"freq_start": 920.0, "freq_end": 925.0, "duty_cycle": 100, "power_limit": 0},
        "IN": {"freq_start": 865.0, "freq_end": 867.0, "duty_cycle": 100, "power_limit": 30},
        "NZ_865": {"freq_start": 864.0, "freq_end": 868.0, "duty_cycle": 100, "power_limit": 36},
        "TH": {"freq_start": 920.0, "freq_end": 925.0, "duty_cycle": 100, "power_limit": 16},
        "UA_433": {"freq_start": 433.0, "freq_end": 434.7, "duty_cycle": 10, "power_limit": 10},
        "UA_868": {"freq_start": 868.0, "freq_end": 868.6, "duty_cycle": 1, "power_limit": 14},
        "MY_433": {"freq_start": 433.0, "freq_end": 435.0, "duty_cycle": 100, "power_limit": 20},
        "MY_919": {"freq_start": 919.0, "freq_end": 924.0, "duty_cycle": 100, "power_limit": 27},
        "SG_923": {"freq_start": 917.0, "freq_end": 925.0, "duty_cycle": 100, "power_limit": 20},
        "LORA_24": {"freq_start": 2400.0, "freq_end": 2483.5, "duty_cycle": 100, "power_limit": 10},
        "UNSET": {"freq_start": 902.0, "freq_end": 928.0, "duty_cycle": 100, "power_limit": 30},
    }

    # Modem presets from freq_calc.ts (bw in kHz)
    MODEM_PRESETS = {
        "SHORT_TURBO": {"bw": 500, "cr": 5, "sf": 7},
        "SHORT_FAST": {"bw": 250, "cr": 5, "sf": 7},
        "SHORT_SLOW": {"bw": 250, "cr": 5, "sf": 8},
        "MEDIUM_FAST": {"bw": 250, "cr": 5, "sf": 9},
        "MEDIUM_SLOW": {"bw": 250, "cr": 5, "sf": 10},
        "LONG_FAST": {"bw": 250, "cr": 5, "sf": 11},
        "LONG_TURBO": {"bw": 500, "cr": 8, "sf": 11},
        "LONG_MODERATE": {"bw": 125, "cr": 8, "sf": 11},
        "LONG_SLOW": {"bw": 125, "cr": 8, "sf": 12},
    }

    # Common style sheet for QGroupBox widgets
    GROUPBOX_STYLE = """
        QGroupBox {
            font-weight: bold;
            border: 1px solid gray;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
    """

    def _create_groupbox(self, title: str) -> QGroupBox:
        """Create a QGroupBox with the common style applied"""
        groupbox = QGroupBox(title)
        groupbox.setStyleSheet(self.GROUPBOX_STYLE)
        return groupbox

    def __init__(self, model: Node, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Node settings")
        self.model = model

        # Create tabs
        self.tabs = QTabWidget()

        # General Tab
        self.general_tab = QWidget()
        self.general_layout = QVBoxLayout(self.general_tab)

        # Port Configurations - GroupBox
        self.port_groupbox = self._create_groupbox("Port Configurations")
        self.port_form = QFormLayout(self.port_groupbox)
        self.web_port = QLineEdit(str(model.web_port))
        self.local_port = QLineEdit(str(model.local_port))
        self.remote_port = QLineEdit(str(model.remote_port))
        self.tcp_port = QLineEdit(str(model.tcp_port))
        self.port_form.addRow("Web server:", self.web_port)
        self.port_form.addRow("Local:", self.local_port)
        self.port_form.addRow("Remote:", self.remote_port)
        self.port_form.addRow("TCP port:", self.tcp_port)

        self.general_layout.addWidget(self.port_groupbox)

        # Position - GroupBox
        self.position_groupbox = self._create_groupbox("Position")
        self.position_form = QFormLayout(self.position_groupbox)
        self.pos_x = QLineEdit(str(int(model.x)))
        self.pos_y = QLineEdit(str(int(model.y)))
        self.position_form.addRow("X:", self.pos_x)
        self.position_form.addRow("Y:", self.pos_y)

        self.general_layout.addWidget(self.position_groupbox)

        self.tabs.addTab(self.general_tab, "General")

        # Initial Hardware Tab
        self.hardware_tab = QWidget()
        self.hardware_layout = QVBoxLayout(self.hardware_tab)

        # Configuration Mode Selection (Preset vs Manual) - GroupBox
        self.config_mode_groupbox = self._create_groupbox("Configuration Mode")
        self.config_mode_layout = QHBoxLayout(self.config_mode_groupbox)
        self.config_mode_group = QButtonGroup(self)
        
        self.preset_radio = QRadioButton("Use Preset")
        self.manual_radio = QRadioButton("Manual")
        self.config_mode_group.addButton(self.preset_radio)
        self.config_mode_group.addButton(self.manual_radio)
        
        self.config_mode_layout.addWidget(self.preset_radio)
        self.config_mode_layout.addWidget(self.manual_radio)
        self.config_mode_layout.addStretch()
        
        self.hardware_layout.addWidget(self.config_mode_groupbox)

        # Preset Selection with Region - GroupBox
        self.preset_groupbox = self._create_groupbox("Preset Selection")
        self.preset_layout = QFormLayout(self.preset_groupbox)
        
        # Region selector (all 20 regions)
        self.region_combo = QComboBox()
        self.region_combo.addItems(list(self.REGIONS.keys()))
        self.preset_layout.addRow("Region", self.region_combo)
        
        # Modem preset selector
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(self.MODEM_PRESETS.keys()))
        self.preset_layout.addRow("Modem Preset", self.preset_combo)
        
        self.hardware_layout.addWidget(self.preset_groupbox)

        # Manual Settings - GroupBox
        self.manual_settings_groupbox = self._create_groupbox("Manual Settings")
        self.manual_settings_layout = QVBoxLayout(self.manual_settings_groupbox)
        
        # Low Level Settings (All dropdowns except LDRO)
        self.low_level_form = QFormLayout()
        
        # Frequency display (MHz) - always uses slot 0
        self.frequency_display = QLabel("-")
        self.low_level_form.addRow("Frequency (MHz)", self.frequency_display)
        
        # Spreading Factor dropdown
        self.spreading_factor = QComboBox()
        self.spreading_factor.addItems(["7", "8", "9", "10", "11", "12"])
        
        # Bandwidth dropdown
        self.bandwidth = QComboBox()
        self.bandwidth.addItems(["62", "125", "250", "500"])
        
        # Code Rate dropdown
        self.code_rate = QComboBox()
        self.code_rate.addItems(["5 (4/5)", "8 (4/8)"])
        
        # LDRO remains as checkbox
        self.ldro_enable = QCheckBox("LDRO Enable")

        self.low_level_form.addRow("Spreading Factor", self.spreading_factor)
        self.low_level_form.addRow("Bandwidth (kHz)", self.bandwidth)
        self.low_level_form.addRow("Code Rate", self.code_rate)
        self.low_level_form.addRow("LDRO Enable", self.ldro_enable)

        self.manual_settings_layout.addLayout(self.low_level_form)
        self.hardware_layout.addWidget(self.manual_settings_groupbox)

        # Frequency Slot Table - GroupBox
        self.slot_table_groupbox = self._create_groupbox("Frequency Slot Table")
        self.slot_table_layout = QVBoxLayout(self.slot_table_groupbox)
        self.slot_table = QTableWidget()
        self.slot_table.setColumnCount(2)
        self.slot_table.setHorizontalHeaderLabels(["Slot", "Frequency (MHz)"])
        self.slot_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.slot_table_layout.addWidget(self.slot_table)
        self.hardware_layout.addWidget(self.slot_table_groupbox)

        # Connect signals
        self.preset_radio.toggled.connect(self._on_config_mode_changed)
        self.manual_radio.toggled.connect(self._on_config_mode_changed)
        self.region_combo.currentIndexChanged.connect(self._on_region_changed)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.bandwidth.currentIndexChanged.connect(self._on_bandwidth_changed)

        # Set default mode (Preset) and populate fields
        self.preset_radio.setChecked(True)
        self._on_preset_changed()  # This will also call _update_slot_table()

        # Load existing model settings if they exist (for edit mode)
        self._load_from_model()

        self.tabs.addTab(self.hardware_tab, "Initial Hardware")

    def _load_from_model(self):
        """Load existing settings from model when editing a node"""
        # Load modem preset if set
        if self.model.modem_preset:
            index = self.preset_combo.findText(self.model.modem_preset)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
        
        # Load region if set
        if self.model.region and self.model.region != "UNSET":
            index = self.region_combo.findText(self.model.region)
            if index >= 0:
                self.region_combo.setCurrentIndex(index)
        
        # Check if model has hardware settings (non-zero values indicate they've been set)
        if self.model.frequency > 0:
            # Set frequency display
            freq_mhz = self.model.frequency / 1000000.0
            self.frequency_display.setText(f"{freq_mhz:.3f}")
        
        if self.model.spreading_factor > 0:
            self.spreading_factor.setCurrentText(str(self.model.spreading_factor))
        
        if self.model.bandwidth > 0:
            self.bandwidth.setCurrentText(str(self.model.bandwidth))
        
        if self.model.code_rate > 0:
            if self.model.code_rate == 5:
                self.code_rate.setCurrentText("5 (4/5)")
            else:
                self.code_rate.setCurrentText("8 (4/8)")
        
        # LDRO is a boolean, so we always set it
        self.ldro_enable.setChecked(self.model.ldro_enable)

        # Final Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        # OK Button
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

    def _calculate_num_channels(self, region: str, bw_khz: int) -> int:
        """Calculate number of channels based on region and bandwidth"""
        region_data = self.REGIONS.get(region, self.REGIONS["UNSET"])
        freq_range = region_data["freq_end"] - region_data["freq_start"]
        bw_mhz = bw_khz / 1000.0
        return int(freq_range / bw_mhz)

    def _calculate_slot_frequency(self, region: str, slot: int, bw_khz: int) -> float:
        """Calculate frequency for a given slot"""
        region_data = self.REGIONS.get(region, self.REGIONS["UNSET"])
        bw_mhz = bw_khz / 1000.0
        return region_data["freq_start"] + (bw_mhz / 2) + (slot * bw_mhz)

    def _update_slot_table(self):
        """Update the frequency slot table based on selected region and bandwidth"""
        region = self.region_combo.currentText()
        bw_khz = int(self.bandwidth.currentText())
        
        num_slots = self._calculate_num_channels(region, bw_khz)
        
        # Update table
        self.slot_table.setRowCount(min(num_slots, 50))  # Limit to 50 rows for performance
        for row in range(min(num_slots, 50)):
            freq_mhz = self._calculate_slot_frequency(region, row, bw_khz)
            self.slot_table.setItem(row, 0, QTableWidgetItem(str(row)))
            self.slot_table.setItem(row, 1, QTableWidgetItem(f"{freq_mhz:.3f}"))

    def _update_frequency_display(self):
        """Update frequency display using slot 0"""
        region = self.region_combo.currentText()
        bw_khz = int(self.bandwidth.currentText())
        freq_mhz = self._calculate_slot_frequency(region, 0, bw_khz)
        self.frequency_display.setText(f"{freq_mhz:.3f}")

    def _on_region_changed(self):
        """Handle region change - update slots and frequencies"""
        region = self.region_combo.currentText()
        preset_name = self.preset_combo.currentText()
        preset = self.MODEM_PRESETS.get(preset_name, self.MODEM_PRESETS["LONG_FAST"])
        
        # Update slot table
        self._update_slot_table()
        
        # Update frequency display
        self._update_frequency_display()

    def _on_config_mode_changed(self):
        """Enable/disable preset combo based on selected mode"""
        is_preset_mode = self.preset_radio.isChecked()
        self.region_combo.setEnabled(is_preset_mode)
        self.preset_combo.setEnabled(is_preset_mode)
        
        # When in preset mode, manual fields are read-only
        self.spreading_factor.setEnabled(not is_preset_mode)
        self.bandwidth.setEnabled(not is_preset_mode)
        self.code_rate.setEnabled(not is_preset_mode)
        self.ldro_enable.setEnabled(not is_preset_mode)

    def _on_preset_changed(self):
        """Update manual fields when preset is selected"""
        if not self.preset_radio.isChecked():
            return
            
        preset_name = self.preset_combo.currentText()
        
        preset = self.MODEM_PRESETS.get(preset_name)
        if not preset:
            return
        
        # Update frequency display
        self._update_frequency_display()
        
        # Set spreading factor
        sf_str = str(preset["sf"])
        self.spreading_factor.setCurrentText(sf_str)
        
        # Set bandwidth
        bw_str = str(preset["bw"])
        self.bandwidth.setCurrentText(bw_str)
        
        # Set code rate
        if preset["cr"] == 5:
            self.code_rate.setCurrentText("5 (4/5)")
        else:
            self.code_rate.setCurrentText("8 (4/8)")
        
        # Update slot table
        self._update_slot_table()

    def _on_bandwidth_changed(self):
        """Handle bandwidth change - update frequency display and slot table"""
        self._update_frequency_display()
        self._update_slot_table()

    def apply(self):
        self.model.web_port = int(self.web_port.text())
        self.model.local_port = int(self.local_port.text())
        self.model.remote_port = int(self.remote_port.text())
        self.model.tcp_port    = int(self.tcp_port.text())
        self.model.x = float(self.pos_x.text())
        self.model.y = float(self.pos_y.text())
        
        # Retrieve values from hardware fields
        # Frequency is calculated from slot 0
        region = self.region_combo.currentText()
        bw_khz = int(self.bandwidth.currentText())
        freq_mhz = self._calculate_slot_frequency(region, 0, bw_khz)
        self.model.frequency = int(freq_mhz * 1000000)
        
        self.model.spreading_factor = int(self.spreading_factor.currentText())
        self.model.bandwidth = int(self.bandwidth.currentText())
        
        # Code rate: extract number from "5 (4/5)" or "8 (4/8)"
        code_rate_text = self.code_rate.currentText()
        self.model.code_rate = int(code_rate_text.split()[0])
        
        self.model.ldro_enable = self.ldro_enable.isChecked()
        
        # Save region, slots count and modem preset
        self.model.region = region
        self.model.slots_count = self._calculate_num_channels(region, bw_khz)
        self.model.modem_preset = self.preset_combo.currentText()

