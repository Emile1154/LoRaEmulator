import json

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QPlainTextEdit,
    QPushButton, QLabel,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


class PacketHistoryDialog(QDialog):
    """Shows received-packet history for one node."""

    COLUMNS = ["Time", "SNR", "RSSI", "msg_str", "raw_data", "wantResp"]

    def __init__(self, node_name: str, monitor, node_model, parent=None):
        super().__init__(parent)
        self._monitor = monitor
        self._node_model = node_model
        self.setWindowTitle(f"Received packets — {node_name}  (max {monitor.__class__.MAX_HISTORY if hasattr(monitor.__class__, 'MAX_HISTORY') else ''})")
        self.resize(820, 500)

        layout = QVBoxLayout(self)

        # Toolbar
        bar = QHBoxLayout()
        self._lbl = QLabel()
        bar.addWidget(self._lbl)
        bar.addStretch()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._populate)
        bar.addWidget(btn_refresh)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        bar.addWidget(btn_close)
        layout.addLayout(bar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.currentItemChanged.connect(lambda cur, _: self._on_row(cur.row() if cur else -1))
        splitter.addWidget(self._table)

        # Detail pane — full packet JSON
        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setFont(QFont("Monospace", 9))
        splitter.addWidget(self._detail)

        splitter.setSizes([300, 200])
        layout.addWidget(splitter)

        self._history: list = []
        self._populate()

    def _populate(self):
        self._history = self._monitor.get_history(self._node_model)
        self._lbl.setText(f"{len(self._history)} packet(s)")
        self._table.setRowCount(len(self._history))
        for row, rec in enumerate(self._history):
            t        = rec["time"].strftime("%H:%M:%S.%f")[:-3]
            snr      = f"{rec['snr']:+.1f}" if rec["snr"] else "N/A"
            rssi     = f"{rec['rssi']:.0f}"  if rec["rssi"] else "N/A"
            msg      = rec["msg_str"][:60]
            raw      = (rec["raw_data"] or b"")[:8].hex(" ") + (
                           " …" if len(rec["raw_data"] or b"") > 8 else "")
            want_ack = "✓" if rec["want_response"] else ""

            for col, val in enumerate([t, snr, rssi, msg, raw, want_ack]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                self._table.setItem(row, col, item)

        self._table.resizeColumnsToContents()
        if self._history:
            self._table.scrollToBottom()
        self._detail.clear()

    def _on_row(self, row: int):
        if 0 <= row < len(self._history):
            try:
                detail = json.dumps(self._history[row]["packet"], default=str, indent=2)
            except Exception:
                detail = str(self._history[row]["packet"])
            self._detail.setPlainText(detail)
