import socket
import struct
import threading
import time

# TCP framing markers
_FRAME_FROM_APP  = 0x3C  # '<' — App Radio
_FRAME_FROM_NODE = 0x3E  # '>' — Radio App

# Commands: App  Radio
CMD_APP_START        = 0x01
CMD_SEND_CHANNEL_MSG = 0x03
CMD_GET_MESSAGE      = 0x0A

# Packets: Radio  App
PACKET_OK                = 0x00
PACKET_ERROR             = 0x01
PACKET_SELF_INFO         = 0x05
PACKET_MSG_SENT          = 0x06
PACKET_CONTACT_MSG       = 0x07
PACKET_CHANNEL_MSG       = 0x08
PACKET_NO_MORE_MSGS      = 0x0A
PACKET_CONTACT_MSG_V3    = 0x10
PACKET_CHANNEL_MSG_V3    = 0x11
PACKET_MESSAGES_WAITING  = 0x83


class MeshCoreCompanionClient:
    """
    TCP companion protocol client for MeshCore nodes.

    Frame format (TCP transport):
      App Radio: 0x3C ('<') + uint16LE(len) + payload
      Radio App: 0x3E ('>') + uint16LE(len) + payload

    Handshake: send CMD_APP_START  receive PACKET_SELF_INFO.
    Unsolicited PACKET_MESSAGES_WAITING triggers automatic polling.
    """

    def __init__(self, host: str = "localhost", port: int = 5000):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._running = False
        self._recv_thread: threading.Thread | None = None

        # Info populated from PACKET_SELF_INFO
        self.device_name: str = ""
        self.frequency_khz: float = 0.0
        self.bandwidth_khz: float = 0.0
        self.spreading_factor: int = 0
        self.coding_rate: int = 0

        # Callbacks — set by caller
        self.on_channel_message = None   # (channel: int, timestamp: int, text: str)
        self.on_contact_message = None   # (sender_hex: str, timestamp: int, text: str)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self, app_name: str = "LoRaEmulator") -> bool:
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=10)
            self.sock.settimeout(None)
            self._running = True

            payload = bytes([CMD_APP_START]) + b'\x00' * 7 + app_name.encode('utf-8')
            self._send_frame(payload)

            resp = self._recv_frame()
            if resp and resp[0] == PACKET_SELF_INFO:
                self._parse_self_info(resp)

            self._recv_thread = threading.Thread(
                target=self._recv_loop,
                daemon=True,
                name=f"meshcore_recv_{self.host}:{self.port}",
            )
            self._recv_thread.start()
            return True
        except Exception as e:
            print(f"[MeshCore] connect {self.host}:{self.port} failed: {e}")
            return False

    def send_channel_message(self, channel: int, text: str) -> bool:
        ts = int(time.time())
        payload = bytes([CMD_SEND_CHANNEL_MSG, 0x00, channel & 0xFF])
        payload += struct.pack('<I', ts)
        payload += text.encode('utf-8')
        try:
            self._send_frame(payload)
            return True
        except Exception:
            return False

    def close(self):
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send_frame(self, payload: bytes):
        header = bytes([_FRAME_FROM_APP]) + struct.pack('<H', len(payload))
        with self._lock:
            self.sock.sendall(header + payload)

    def _recv_frame(self) -> bytes | None:
        try:
            header = b''
            while len(header) < 3:
                chunk = self.sock.recv(3 - len(header))
                if not chunk:
                    return None
                header += chunk
            if header[0] != _FRAME_FROM_NODE:
                return None
            length = struct.unpack('<H', header[1:3])[0]
            data = b''
            while len(data) < length:
                chunk = self.sock.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            return data
        except Exception:
            return None

    def _recv_loop(self):
        while self._running:
            frame = self._recv_frame()
            if frame is None:
                break
            self._dispatch(frame)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, frame: bytes):
        if not frame:
            return
        pkt = frame[0]
        if pkt == PACKET_MESSAGES_WAITING:
            self._poll_messages()
        elif pkt == PACKET_CHANNEL_MSG:
            self._on_channel_msg(frame)
        elif pkt == PACKET_CHANNEL_MSG_V3:
            self._on_channel_msg_v3(frame)
        elif pkt == PACKET_CONTACT_MSG:
            self._on_contact_msg(frame)
        elif pkt == PACKET_CONTACT_MSG_V3:
            self._on_contact_msg_v3(frame)

    def _poll_messages(self):
        while self._running:
            try:
                self._send_frame(bytes([CMD_GET_MESSAGE]))
            except Exception:
                break
            frame = self._recv_frame()
            if frame is None or frame[0] == PACKET_NO_MORE_MSGS:
                break
            self._dispatch(frame)

    # ------------------------------------------------------------------
    # Packet parsers
    # ------------------------------------------------------------------

    def _on_channel_msg(self, frame: bytes):
        # [0x08][channel][path_len][text_type][ts:4][text...]
        if len(frame) < 9:
            return
        channel = frame[1]
        timestamp = struct.unpack('<I', frame[4:8])[0]
        text = frame[8:].decode('utf-8', errors='replace')
        if self.on_channel_message:
            self.on_channel_message(channel, timestamp, text)

    def _on_channel_msg_v3(self, frame: bytes):
        # [0x11][snr][rsv:2][channel][path_len][text_type][ts:4][text...]
        if len(frame) < 12:
            return
        channel = frame[4]
        timestamp = struct.unpack('<I', frame[7:11])[0]
        text = frame[11:].decode('utf-8', errors='replace')
        if self.on_channel_message:
            self.on_channel_message(channel, timestamp, text)

    def _on_contact_msg(self, frame: bytes):
        # [0x07][key:6][path_len][text_type][ts:4][sig?:4][text...]
        if len(frame) < 14:
            return
        sender = frame[1:7].hex()
        text_type = frame[8]
        timestamp = struct.unpack('<I', frame[9:13])[0]
        text_start = 17 if text_type == 2 else 13
        text = frame[text_start:].decode('utf-8', errors='replace')
        if self.on_contact_message:
            self.on_contact_message(sender, timestamp, text)

    def _on_contact_msg_v3(self, frame: bytes):
        # [0x10][snr][rsv:2][key:6][path_len][text_type][ts:4][sig?:4][text...]
        if len(frame) < 17:
            return
        sender = frame[4:10].hex()
        text_type = frame[11]
        timestamp = struct.unpack('<I', frame[12:16])[0]
        text_start = 20 if text_type == 2 else 16
        text = frame[text_start:].decode('utf-8', errors='replace')
        if self.on_contact_message:
            self.on_contact_message(sender, timestamp, text)

    def _parse_self_info(self, frame: bytes):
        # [0x05][adv_type][tx_pwr][max_tx_pwr][key:32][lat:4][lon:4]
        # [multi_acks][loc_policy][telem][manual_add]
        # [freq:4][bw:4][sf][cr][name...]
        if len(frame) > 58:
            self.device_name = frame[58:].decode('utf-8', errors='replace')
        if len(frame) >= 58:
            freq_raw = struct.unpack('<I', frame[48:52])[0]
            bw_raw   = struct.unpack('<I', frame[52:56])[0]
            self.frequency_khz  = freq_raw / 1000.0
            self.bandwidth_khz  = bw_raw  / 1000.0
            self.spreading_factor = frame[56]
            self.coding_rate      = frame[57]
