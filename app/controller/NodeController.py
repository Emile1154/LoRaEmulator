import random
import threading
import webbrowser

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QGraphicsScene, QMessageBox, QPlainTextEdit

from model.Node import Node, State
from model.Project import ProjectModel
from view.NodeItem import NodeItem
from view.dialogs import NodeDialog


class NodeController(QObject):
    _node_crashed      = pyqtSignal(object, str)   # NodeItem (or None), last_logs
    _node_enable_done  = pyqtSignal(object, int)   # NodeItem, result_code
    _node_disable_done = pyqtSignal(object)        # NodeItem
    _node_delete_done  = pyqtSignal(object)        # NodeItem
    _node_log_signal   = pyqtSignal(str)           # log line from Node.logger()

    def __init__(self, project_model: ProjectModel, scene: QGraphicsScene,
                 node_console: QPlainTextEdit = None):
        super().__init__()
        self.project = project_model
        self.scene = scene
        self._node_console = node_console
        self.packet_monitor = None  # set from main.py after construction
        self._node_crashed.connect(self._show_crash_alert)
        self._node_enable_done.connect(self._on_enable_done)
        self._node_disable_done.connect(lambda item: item.setStatus(State.STOPPED))
        self._node_delete_done.connect(self._finish_delete)
        if node_console is not None:
            self._node_log_signal.connect(self._append_node_log)

    def _append_node_log(self, msg: str):
        self._node_console.appendPlainText(msg)

    def _log_node(self, msg: str):
        self._node_log_signal.emit(msg)

    def register_node(self, item: NodeItem):
        item.model.log_fn = self._log_node
        if self.packet_monitor is not None:
            self.packet_monitor.register_node(item.model)
    
    def generate_MAC(self):
        mac = [random.randint(0x00, 0xFF) for _ in range(6)]
        mac_address = ''.join(f'{byte:02x}' for byte in mac)
        return mac_address.upper() 

    def create_node(self, x, y, parent):
        model = Node(x, y, MAC_address=self.generate_MAC())
        dlg = NodeDialog(model, parent)
        if dlg.exec():
            dlg.apply()
            self.project.nodes.append(model)
            item = NodeItem(model, self)
            self.register_node(item)
            self.project.gui_nodes.append(item)
            self.scene.addItem(item)

    def edit_node(self, item: NodeItem):
        dlg = NodeDialog(item.model)
        if dlg.exec():
            dlg.apply()
            item.setPos(item.model.x, item.model.y)

    def _on_node_crash(self, node: Node, logs: str):
        item = next((i for i in self.project.gui_nodes if i.model is node), None)
        self._node_crashed.emit(item, logs)

    def _show_crash_alert(self, item, logs: str):
        if item is not None:
            item.setStatus(State.ERROR)
        container_name = item.model.container_name if item else "unknown"
        msg = QMessageBox()
        msg.setWindowTitle(f"Node crashed: {container_name}")
        msg.setText(f"Container <b>{container_name}</b> exited unexpectedly.")
        msg.setDetailedText(logs or "(no logs captured)")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.exec()

    def _on_enable_done(self, item: NodeItem, res: int):
        # Ignore stale result: node was stopped/deleted while enable was in-flight
        if item.model.state in (State.STOPPING, State.STOPPED, State.ERROR):
            return
        if res in (0, 2):  # 0=started, 2=already running
            item.setStatus(State.RUNNING)
        else:
            item.setStatus(State.ERROR)

    def enable_node(self, item: NodeItem):
        item.setStatus(State.STARTING)

        def _on_container_started():
            self._node_enable_done.emit(item, 0)

        def _run():
            try:
                res = item.model.enable(
                    on_crash=self._on_node_crash,
                    on_started=_on_container_started,
                )
            except Exception as e:
                print(f"[ERROR] enable failed for {item.model.container_name}: {e}")
                res = -1
            # on_started already handled res=0; only emit for errors or already-running (res=2)
            if res != 0:
                self._node_enable_done.emit(item, res)

        threading.Thread(
            target=_run,
            daemon=True,
            name=f"enable_{item.model.container_name}",
        ).start()

    def disable_node(self, item: NodeItem):
        item.setStatus(State.STOPPING)

        def _run():
            try:
                item.model.shutdown()
            except Exception as e:
                print(f"[ERROR] shutdown failed for {item.model.container_name}: {e}")
            self._node_disable_done.emit(item)

        threading.Thread(
            target=_run,
            daemon=True,
            name=f"disable_{item.model.container_name}",
        ).start()

    def _finish_delete(self, item: NodeItem):
        item.setStatus(State.STOPPED)
        try:
            self.project.nodes.remove(item.model)
        except ValueError:
            pass
        try:
            self.project.gui_nodes.remove(item)
        except ValueError:
            pass
        self.scene.removeItem(item)

    def delete_node(self, item: NodeItem):
        item.setStatus(State.STOPPING)

        def _run():
            try:
                item.model.shutdown()
            except Exception as e:
                print(f"[ERROR] delete/shutdown failed for {item.model.container_name}: {e}")
            self._node_delete_done.emit(item)

        threading.Thread(
            target=_run,
            daemon=True,
            name=f"delete_{item.model.container_name}",
        ).start()

    def send_ping(self, from_item: NodeItem, to_item: NodeItem):
        def _run():
            from_item.model.send_ping(to_item.model)
        threading.Thread(target=_run, daemon=True,
                         name=f"ping_{from_item.model.container_name}").start()

    def show_received(self, item: NodeItem):
        if self.packet_monitor is None:
            return
        from PyQt6.QtWidgets import QApplication
        from view.PacketHistoryDialog import PacketHistoryDialog
        dlg = PacketHistoryDialog(
            item.model.short_mac(),
            self.packet_monitor,
            item.model,
            parent=QApplication.activeWindow(),
        )
        dlg.exec()

    def send_message_dialog(self, from_item: NodeItem, to_item: NodeItem):
        from PyQt6.QtWidgets import QInputDialog, QApplication
        parent = QApplication.activeWindow()
        
        dlg = QInputDialog(parent)
        dlg.setFixedSize(800, 150)
        text, ok = dlg.getText(
            parent,
            "Send Message",
            f"{from_item.model.short_mac()} -> {to_item.model.short_mac()}:",
        )
        if ok and text.strip():
            self.send_message(from_item, to_item, text.strip())

    def send_message(self, from_item: NodeItem, to_item: NodeItem, text: str):
        def _run():
            from_item.model.send_message(to_item.model, text)
        threading.Thread(target=_run, daemon=True,
                         name=f"msg_{from_item.model.container_name}").start()

    def connect_api_client(self, item: NodeItem):
        def _run():
            item.model.connect_api_client()
            if self.packet_monitor is not None:
                self.packet_monitor.ensure_subscribed()
        threading.Thread(target=_run, daemon=True,
                         name=f"api_connect_{item.model.container_name}").start()

    def disconnect_api_client(self, item: NodeItem):
        def _run():
            item.model.disconnect_api_client()
        threading.Thread(target=_run, daemon=True,
                         name=f"api_disconnect_{item.model.container_name}").start()

    def launch_all(self):
        for node in self.project.gui_nodes:
            self.enable_node(node)

    def shutdown_all(self):
        """Shutdown all nodes in parallel; blocks until all are done (max 10s each)."""
        threads = []
        for item in self.project.gui_nodes:
            item.setStatus(State.STOPPING)
            t = threading.Thread(
                target=item.model.shutdown,
                daemon=True,
                name=f"shutdown_{item.model.container_name}",
            )
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=10)
        for item in self.project.gui_nodes:
            item.setStatus(State.STOPPED)

    def update_position(self, item: NodeItem, pos):
        item.model.x = pos.x()
        item.model.y = pos.y()

    def open_web(self, item: NodeItem):
        print(f"Open web interface on port {item.model.web_port}")
        webbrowser.open(f"http://localhost:{item.model.web_port}")

    def open_terminal(self, item: NodeItem, setup):
        print(f"Open terminal for node {item.model.local_port}")
        if setup:
            item.model.open_shell_setup()    
            return
        item.model.open_shell()