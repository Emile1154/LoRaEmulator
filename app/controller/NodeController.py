
from model.Project import ProjectModel
from PyQt6.QtWidgets import QGraphicsScene
from model.Node import Node, State
from view.NodeItem import NodeItem
from view.dialogs import NodeDialog
import random
import webbrowser
class NodeController:
    def __init__(self, project_model: ProjectModel, scene: QGraphicsScene):
        self.project = project_model
        self.scene = scene
    
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
            self.project.gui_nodes.append(item)
            self.scene.addItem(item)

    def edit_node(self, item: NodeItem):
        dlg = NodeDialog(item.model)
        if dlg.exec():
            dlg.apply()
            item.setPos(item.model.x, item.model.y)

    def enable_node(self, item: NodeItem):
        item.setStatus(State.STARTING)
        res = item.model.enable()
        if res == 0:
            item.setStatus(State.RUNNING)
        else:
            item.setStatus(State.ERROR)

    def disable_node(self, item: NodeItem):
        item.setStatus(State.STOPPING)
        item.model.shutdown()
        item.setStatus(State.STOPPED)
    
    def delete_node(self, item: NodeItem):
        self.disable_node(item)
        try:
            self.project.nodes.remove(item.model)
        except ValueError:
            pass
        try:
            self.project.gui_nodes.remove(item)
        except ValueError:
            pass
        self.scene.removeItem(item)

    def launch_all(self):
        for node in self.project.gui_nodes:
            self.enable_node(node)

    def shutdown_all(self):
        """Shutdown all nodes in the project."""
        for node in self.project.gui_nodes:
            self.disable_node(node)

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