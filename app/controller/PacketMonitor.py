import base64
import datetime
import math
from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal

MAX_HISTORY = 500
MAX_TRANSFERS = 2000

# Packet types for visualization
PKT_TYPE_DATA = "data"
PKT_TYPE_ACK = "ack"


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


def _get_packet_type(packet: dict) -> str:
    """Determine if packet is DATA or ACK"""
    decoded = packet.get("decoded", {})
    portnum = decoded.get("portnum", "")

    # ACK / routing packets are ROUTING_APP (errorReason NONE == positive ACK)
    if portnum == "ROUTING_APP":
        return PKT_TYPE_ACK

    return PKT_TYPE_DATA


class PacketMonitor(QObject):
    """
    Correlates per-node TX/RX events (every node has its own interface and
    reports every radio packet it hears) into logical end-to-end transfers.

    Drawing model (Variant A — each hop is drawn by the node that received it):
      * origin TX                -> TX overlay + pending "delivery" arrow orig->dest
      * intermediate RX (to!=me) -> RX + RETX overlay + relay hop arrow relayNode->me
      * final RX     (to==me)    -> RX overlay; confirm delivery arrow
                                    (immediately if wantAck==0, else wait for ACK)
      * ACK reaches origin       -> ACK arrow acker->orig + confirm delivery arrow
      * delivery timeout         -> delivery arrow turns red + "Packet Missed" overlay
    """

    # overlay on a node:  node_idx, kind(TX/RX/RETX), snr, rssi, msg, raw, want_ack
    overlay_event = pyqtSignal(int, str, float, float, str, object, bool)
    # arrow command:      action(data/relay/ack/delivered/confirm), a_idx, b_idx, key
    arrow_event = pyqtSignal(str, int, int, str)

    def __init__(self, project_model):
        super().__init__()
        self._project = project_model
        self._history: dict[int, deque] = {}
        # (from_num, packet_id) -> {orig, dest, want_ack, delivered, acked}
        self._transfers: dict[tuple, dict] = {}

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

    # ---- index helpers -------------------------------------------------

    @staticmethod
    def _idx_by_id(nodes, node_num: int) -> int:
        if not node_num:
            return -1
        return next(
            (i for i, it in enumerate(nodes)
             if _node_id(it.model.MAC_address) == node_num),
            -1,
        )

    @staticmethod
    def _idx_by_byte(nodes, last_byte: int) -> int:
        if not last_byte:
            return -1
        return next(
            (i for i, it in enumerate(nodes)
             if (_node_id(it.model.MAC_address) & 0xFF) == last_byte),
            -1,
        )

    @staticmethod
    def _self_idx(nodes, node_model) -> int:
        return next((i for i, it in enumerate(nodes) if it.model is node_model), -1)

    # ---- main entry ----------------------------------------------------

    def _handle(self, node_model, packet, is_tx: bool = False):
        nodes = self._project.gui_nodes
        self_idx = self._self_idx(nodes, node_model)
        if self_idx == -1:
            return

        snr = _safe_float(packet.get("rxSnr") or packet.get("rx_snr"))
        rssi = _safe_float(packet.get("rxRssi") or packet.get("rx_rssi"))
        pkt_type = _get_packet_type(packet)
        pid = packet.get("id", 0)

        if "decoded" in packet:
            decoded = packet.get("decoded") or {}
            raw_data = decoded.get("payload") or b""
            msg_str = _bytes_to_str(raw_data)
            want_ack = bool(packet.get("wantAck", False))
        else:
            enc = packet.get("encrypted", b"")
            try:
                raw_data = base64.b64decode(enc) if isinstance(enc, str) else bytes(enc)
            except Exception:
                raw_data = b""
            msg_str = _bytes_to_str(raw_data)
            want_ack = bool(packet.get("wantAck", False))

        # --- history (used by "View received packets") ---
        if is_tx:
            tx_idx, rx_idx = self_idx, self._idx_by_id(nodes, packet.get("to", 0))
        else:
            tx_idx, rx_idx = self._idx_by_id(nodes, packet.get("from", 0)), self_idx
        record = {
            "time": datetime.datetime.now(),
            "tx_idx": tx_idx, "rx_idx": rx_idx,
            "snr": snr, "rssi": rssi,
            "msg_str": msg_str, "raw_data": raw_data,
            "want_response": want_ack, "is_tx": is_tx,
            "packet": packet, "pkt_type": pkt_type,
        }
        key = id(node_model)
        if key not in self._history:
            self._history[key] = deque(maxlen=MAX_HISTORY)
        self._history[key].append(record)

        # --- visualization ---
        if is_tx:
            self._handle_tx(nodes, node_model, self_idx, packet, pid,
                            want_ack, msg_str, raw_data, pkt_type)
        else:
            self._handle_rx(nodes, self_idx, packet, pid, want_ack,
                            snr, rssi, msg_str, raw_data, pkt_type)

    # ---- TX (origination at the source node) ---------------------------

    def _handle_tx(self, nodes, node_model, self_idx, packet, pid,
                   want_ack, msg_str, raw_data, pkt_type):
        # A node also "hears" its own packet when a neighbour rebroadcasts it
        # (from == us, relayNode == neighbour). Only the first, genuine
        # origination starts a transfer; later echoes are ignored here.
        if pkt_type == PKT_TYPE_ACK:
            return  # ACKs are handled when they reach the origin

        from_num = _node_id(node_model.MAC_address)
        tkey = (from_num, pid)
        if tkey in self._transfers:
            return  # overheard our own relayed packet

        dest_idx = self._idx_by_id(nodes, packet.get("to", 0))
        self._transfers[tkey] = {
            "orig": self_idx, "dest": dest_idx,
            "want_ack": want_ack, "delivered": False, "acked": False,
        }
        self._prune_transfers()

        self.overlay_event.emit(self_idx, "TX", 0.0, 0.0, msg_str, raw_data, want_ack)

        if 0 <= dest_idx and dest_idx != self_idx:
            self.arrow_event.emit("data", self_idx, dest_idx, self._dkey(tkey))

    # ---- RX (a node received a hop) ------------------------------------

    def _handle_rx(self, nodes, self_idx, packet, pid, want_ack,
                   snr, rssi, msg_str, raw_data, pkt_type):
        from_num = packet.get("from", 0)
        to_num = packet.get("to", 0)
        to_idx = self._idx_by_id(nodes, to_num)
        is_final = (to_idx == self_idx)

        # previous hop = whoever transmitted this copy (relay_node last byte)
        relay_byte = packet.get("relayNode", 0)
        prev_idx = self._idx_by_byte(nodes, relay_byte)
        if prev_idx == -1:
            prev_idx = self._idx_by_id(nodes, from_num)

        if pkt_type == PKT_TYPE_ACK:
            # Only meaningful once the ACK gets back to the original sender.
            if is_final:
                req_id = (packet.get("decoded") or {}).get("requestId", 0)
                tkey = (to_num, req_id)
                self.overlay_event.emit(self_idx, "ACK", snr, rssi, msg_str, raw_data, want_ack)
                if prev_idx >= 0 and prev_idx != self_idx:
                    self.arrow_event.emit("ack", prev_idx, self_idx, self._akey(tkey))
                tr = self._transfers.get(tkey)
                if tr is not None:
                    tr["acked"] = True
                self.arrow_event.emit("confirm", -1, -1, self._dkey(tkey))
            return

        # ---- DATA ----
        tkey = (from_num, pid)
        tr = self._transfers.get(tkey)
        orig_idx = tr["orig"] if tr else self._idx_by_id(nodes, from_num)

        if is_final:
            self.overlay_event.emit(self_idx, "RX", snr, rssi, msg_str, raw_data, want_ack)
            if tr is not None:
                tr["delivered"] = True

            # Show the last hop explicitly when it came via a relay.
            if prev_idx >= 0 and prev_idx != self_idx and prev_idx != orig_idx:
                self.arrow_event.emit("relay", prev_idx, self_idx,
                                      self._rkey(tkey, prev_idx, self_idx))

            if tr is None:
                # Origin TX was never seen — draw a stand-alone hop so the
                # reception is still visible.
                if prev_idx >= 0 and prev_idx != self_idx:
                    self.arrow_event.emit("relay", prev_idx, self_idx,
                                          self._rkey(tkey, prev_idx, self_idx))
            elif not want_ack:
                self.arrow_event.emit("confirm", -1, -1, self._dkey(tkey))
            else:
                # Delivered, but waiting for the ACK to confirm the path.
                self.arrow_event.emit("delivered", -1, -1, self._dkey(tkey))
        else:
            # Intermediate relay node: it received a packet addressed elsewhere
            # and will rebroadcast it -> RX + RETX.
            self.overlay_event.emit(self_idx, "RX", snr, rssi, msg_str, raw_data, want_ack)
            self.overlay_event.emit(self_idx, "RETX", snr, rssi, msg_str, raw_data, want_ack)
            if prev_idx >= 0 and prev_idx != self_idx:
                self.arrow_event.emit("relay", prev_idx, self_idx,
                                      self._rkey(tkey, prev_idx, self_idx))

    # ---- key helpers ---------------------------------------------------

    @staticmethod
    def _dkey(tkey) -> str:
        return f"d:{tkey[0]}:{tkey[1]}"

    @staticmethod
    def _akey(tkey) -> str:
        return f"a:{tkey[0]}:{tkey[1]}"

    @staticmethod
    def _rkey(tkey, a, b) -> str:
        return f"r:{tkey[0]}:{tkey[1]}:{a}:{b}"

    def _prune_transfers(self):
        if len(self._transfers) <= MAX_TRANSFERS:
            return
        # Drop the oldest finished transfers first, then plain oldest.
        for k in list(self._transfers.keys()):
            if len(self._transfers) <= MAX_TRANSFERS:
                break
            t = self._transfers[k]
            if t.get("acked") or t.get("delivered"):
                del self._transfers[k]
        while len(self._transfers) > MAX_TRANSFERS:
            self._transfers.pop(next(iter(self._transfers)))
