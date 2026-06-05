import base64
import datetime
import math
from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal

MAX_HISTORY = 500


def _node_id(mac: str) -> int:
    try:
        return int(mac.replace(":", "")[4:], 16)
    except ValueError:
        return -1


def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _bytes_to_str(raw: bytes) -> str:
    if not raw:
        return ""
    return raw.decode("utf-8", errors="replace")


class PacketMonitor(QObject):
    # tx_idx, rx_idx, snr_dB, rssi_dBm, msg_str, raw_data, want_response, is_tx
    packet_event = pyqtSignal(int, int, float, float, str, object, bool, bool)

    def __init__(self, project_model):
        super().__init__()
        self._project = project_model
        self._history: dict[int, deque] = {}

    def register_node(self, node_model):
        def _cb_rx(packet):
            self._handle(node_model, packet, is_tx=False)
        def _cb_tx(packet):
            self._handle(node_model, packet, is_tx=True)
        node_model.packet_received_cb = _cb_rx
        node_model.packet_sent_cb = _cb_tx

    def get_history(self, node_model) -> list:
        return list(self._history.get(id(node_model), []))

    def ensure_subscribed(self):
        pass

    def _handle(self, node_model, packet, is_tx: bool = False):
        nodes = self._project.gui_nodes

        if is_tx:
            tx_idx = next(
                (i for i, item in enumerate(nodes) if item.model is node_model), -1
            )
            to_id = packet.get("to", 0)
            rx_idx = next(
                (i for i, item in enumerate(nodes)
                 if _node_id(item.model.MAC_address) == to_id),
                -1,
            )
        else:
            rx_idx = next(
                (i for i, item in enumerate(nodes) if item.model is node_model), -1
            )
            if rx_idx == -1:
                return
            from_id = packet.get("from", 0)
            tx_idx = next(
                (i for i, item in enumerate(nodes)
                 if _node_id(item.model.MAC_address) == from_id),
                -1,
            )

        snr  = _safe_float(packet.get("rxSnr")  or packet.get("rx_snr"))
        rssi = _safe_float(packet.get("rxRssi") or packet.get("rx_rssi"))

        if "decoded" in packet:
            decoded       = packet.get("decoded") or {}
            raw_data      = decoded.get("payload") or b""
            msg_str       = _bytes_to_str(raw_data)
            want_response = bool(packet.get("wantAck", False))
        else:
            enc = packet.get("encrypted", b"")
            try:
                raw_data = base64.b64decode(enc) if isinstance(enc, str) else bytes(enc)
            except Exception:
                raw_data = b""
            msg_str       = _bytes_to_str(raw_data)
            want_response = packet.get("wantAck", False)

        record = {
            "time":          datetime.datetime.now(),
            "tx_idx":        tx_idx,
            "rx_idx":        rx_idx,
            "snr":           snr,
            "rssi":          rssi,
            "msg_str":       msg_str,
            "raw_data":      raw_data,
            "want_response": want_response,
            "is_tx":         is_tx,
            "packet":        packet,
        }
        key = id(node_model)
        if key not in self._history:
            self._history[key] = deque(maxlen=MAX_HISTORY)
        self._history[key].append(record)

        self.packet_event.emit(tx_idx, rx_idx, snr, rssi, msg_str, raw_data, want_response, is_tx)
