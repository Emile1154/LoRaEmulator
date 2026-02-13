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
        self.file_path = None

    def to_json(self) -> str:
        def serialize_node(node):
            data = asdict(node)
            # Convert State enum to its integer value
            data['state'] = node.state.value
            return data
        return json.dumps([serialize_node(n) for n in self.nodes], indent=4)

    def from_json(self, text: str):
        self.clear()
        for item in json.loads(text):
            # Convert state integer back to State enum
            item['state'] = State(item['state'])
            self.nodes.append(Node(**item))
