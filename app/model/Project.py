from model.Node import Node, State
from view.NodeItem import NodeItem
import json
from dataclasses import dataclass, asdict
class ProjectModel:
    def __init__(self):
        self.nodes: list[Node] = []
        self.gui_nodes: list[NodeItem] = []
        self.file_path: str = None

    def clear(self):
        self.nodes.clear()
        self.gui_nodes.clear()
        self.file_path = None

    def to_json(self) -> str:
        def serialize_node(node):
            data = asdict(node)
            data.pop('state', None)  # runtime state is not persisted
            return data
        return json.dumps([serialize_node(n) for n in self.nodes], indent=4)

    def from_json(self, text: str):
        self.clear()
        for item in json.loads(text):
            # Always start as CREATED — saved runtime state is meaningless after restart
            item['state'] = State.CREATED
            # Backwards compatibility: old project files lack network_type
            item.setdefault('network_type', 'meshtastic')
            item.setdefault('noise_std', 2e-6)
            self.nodes.append(Node(**item))
