import base64
import datetime
import math
from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal

MAX_HISTORY = 500
MAX_TRANSFERS = 2000
DEBUG = True

HOP_DELAY_MS = 450  # stagger the second reconstructed hop so the path animates
BROADCAST_NUM = 0xFFFFFFFF

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
    if portnum == "ROUTING_APP":
        return PKT_TYPE_ACK
    return PKT_TYPE_DATA


class PacketMonitor(QObject):
    """
    Builds the packet-flow visualization from the events Meshtastic actually
    exposes to a node's client.

    Observability (verified against this firmware): a node only hands its
    client the packets that are *for it* or broadcast.  A pure relay node
    therefore reports **nothing** about packets it merely forwards.  What we do
    get for a unicast A -> (R) -> B exchange is:

        * at A:  the outgoing/overheard copy  (from=A)
        * at B:  the delivered copy           (to=B,  relayNode = last relayer)
        * at A:  the returning ACK            (to=A,  relayNode = last relayer)

    The ``relayNode`` byte names whoever physically transmitted that copy, so
    the relay hop is *reconstructed* from it:

        relayNode == sender   -> direct      A -> B
        relayNode == some R    -> via relay   A -> R -> B   (+ RETX at R)

    NOTE: ``relayNode`` is a single byte for the *last* relayer only, so a chain
    deeper than one hop (A -> R1 -> R2 -> B) collapses to A -> R2 -> B — the
    protocol does not carry the full path.
    """

    # overlay on a node:  node_idx, kind(TX/RX/RETX/ACK), snr, rssi, msg, raw, want_ack
    overlay_event = pyqtSignal(int, str, float, float, str, object, bool)
    # arrow command:      action(data/hop/ack/delivered/confirm/cancel), a, b, key, delay_ms
    arrow_event = pyqtSignal(str, int, int, str, int)

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

        if DEBUG:
            print(
                f"[PM] {'TX' if is_tx else 'RX'} self={node_model.short_mac()} "
                f"from={packet.get('from')} to={packet.get('to')} "
                f"id={pid} relay={packet.get('relayNode')} type={pkt_type} ack={want_ack}"
            )

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
        # ACKs are auto-generated and surface only when received downstream.
        if pkt_type == PKT_TYPE_ACK:
            return

        from_num = _node_id(node_model.MAC_address)
        tkey = (from_num, pid)
        if tkey in self._transfers:
            return  # overheard our own packet being relayed back

        dest_idx = self._idx_by_id(nodes, packet.get("to", 0))
        self._transfers[tkey] = {
            "orig": self_idx, "dest": dest_idx,
            "want_ack": want_ack, "delivered": False, "acked": False,
        }
        self._prune_transfers()

        self.overlay_event.emit(self_idx, "TX", 0.0, 0.0, msg_str, raw_data, want_ack)
        # Provisional end-to-end arrow: confirms on direct delivery, is replaced
        # by the reconstructed path on relayed delivery, or turns red on timeout.
        if 0 <= dest_idx and dest_idx != self_idx:
            self.arrow_event.emit("data", self_idx, dest_idx, self._dkey(tkey), 0)

    # ---- RX (only the destination / original sender ever get here) ------

    def _handle_rx(self, nodes, self_idx, packet, pid, want_ack,
                   snr, rssi, msg_str, raw_data, pkt_type):
        from_num = packet.get("from", 0)
        to_num = packet.get("to", 0)
        from_idx = self._idx_by_id(nodes, from_num)
        to_idx = self._idx_by_id(nodes, to_num)
        is_final = (to_idx == self_idx)

        relay_byte = packet.get("relayNode", 0)
        relay_idx = self._idx_by_byte(nodes, relay_byte)

        if pkt_type == PKT_TYPE_ACK:
            if is_final:
                self._reconstruct_ack(self_idx, from_idx, relay_idx, to_num, packet,
                                      snr, rssi, msg_str, raw_data, want_ack)
            return

        # Broadcast: the firmware delivers it to *every* node's client, so each
        # reception is real — draw the hop relayNode->me with RX + RETX (every
        # node both hears and re-floods a broadcast). Works at any depth.
        if to_num == BROADCAST_NUM:
            prev_idx = relay_idx if relay_idx >= 0 else from_idx
            self.overlay_event.emit(self_idx, "RX", snr, rssi, msg_str, raw_data, want_ack)
            self.overlay_event.emit(self_idx, "RETX", snr, rssi, msg_str, raw_data, want_ack)
            if prev_idx >= 0 and prev_idx != self_idx:
                self.arrow_event.emit("hop", prev_idx, self_idx,
                                      self._hkey((from_num, pid), prev_idx, self_idx), 0)
            return

        # DATA (unicast) — relays are silent, so only the destination reaches here.
        if not is_final:
            return

        tkey = (from_num, pid)
        tr = self._transfers.get(tkey)
        orig_idx = tr["orig"] if tr is not None else from_idx
        if tr is not None:
            tr["delivered"] = True

        self.overlay_event.emit(self_idx, "RX", snr, rssi, msg_str, raw_data, want_ack)

        if relay_idx < 0 or relay_idx == orig_idx:
            # Direct delivery — drive the provisional orig->dest arrow.
            action = "delivered" if want_ack else "confirm"
            self.arrow_event.emit(action, -1, -1, self._dkey(tkey), 0)
            return

        # Relayed delivery: reconstruct orig -> R -> dest.
        self.arrow_event.emit("cancel", -1, -1, self._dkey(tkey), 0)
        if orig_idx >= 0 and orig_idx != relay_idx:
            self.arrow_event.emit("hop", orig_idx, relay_idx,
                                  self._hkey(tkey, orig_idx, relay_idx), 0)
        self.overlay_event.emit(relay_idx, "RETX", snr, rssi, msg_str, raw_data, want_ack)
        if relay_idx != self_idx:
            self.arrow_event.emit("hop", relay_idx, self_idx,
                                  self._hkey(tkey, relay_idx, self_idx), HOP_DELAY_MS)

    def _reconstruct_ack(self, self_idx, from_idx, relay_idx, to_num, packet,
                         snr, rssi, msg_str, raw_data, want_ack):
        # self == original sender (A); from == acknowledger (B)
        req_id = (packet.get("decoded") or {}).get("requestId", 0)
        tkey = (to_num, req_id)
        tr = self._transfers.get(tkey)
        if tr is not None:
            tr["acked"] = True

        # ACK sent (at B) and received (at A)
        if from_idx >= 0 and from_idx != self_idx:
            self.overlay_event.emit(from_idx, "ACK", 0.0, 0.0, "", b"", False)
        self.overlay_event.emit(self_idx, "ACK", snr, rssi, msg_str, raw_data, want_ack)

        # Confirm the forward data arrow (direct case turns it blue).
        self.arrow_event.emit("confirm", -1, -1, self._dkey(tkey), 0)

        if relay_idx < 0 or relay_idx == from_idx:
            # Direct ACK B -> A
            if from_idx >= 0 and from_idx != self_idx:
                self.arrow_event.emit("ack", from_idx, self_idx,
                                      self._kkey(tkey, from_idx, self_idx), 0)
            return

        # Relayed ACK B -> R -> A
        if from_idx >= 0 and from_idx != relay_idx:
            self.arrow_event.emit("ack", from_idx, relay_idx,
                                  self._kkey(tkey, from_idx, relay_idx), 0)
        self.overlay_event.emit(relay_idx, "RETX", snr, rssi, msg_str, raw_data, want_ack)
        if relay_idx != self_idx:
            self.arrow_event.emit("ack", relay_idx, self_idx,
                                  self._kkey(tkey, relay_idx, self_idx), HOP_DELAY_MS)

    # ---- key helpers ---------------------------------------------------

    @staticmethod
    def _dkey(tkey) -> str:
        return f"d:{tkey[0]}:{tkey[1]}"

    @staticmethod
    def _hkey(tkey, a, b) -> str:
        return f"h:{tkey[0]}:{tkey[1]}:{a}:{b}"

    @staticmethod
    def _kkey(tkey, a, b) -> str:
        return f"k:{tkey[0]}:{tkey[1]}:{a}:{b}"

    def _prune_transfers(self):
        if len(self._transfers) <= MAX_TRANSFERS:
            return
        for k in list(self._transfers.keys()):
            if len(self._transfers) <= MAX_TRANSFERS:
                break
            t = self._transfers[k]
            if t.get("acked") or t.get("delivered"):
                del self._transfers[k]
        while len(self._transfers) > MAX_TRANSFERS:
            self._transfers.pop(next(iter(self._transfers)))
