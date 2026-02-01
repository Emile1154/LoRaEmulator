from model.Node import Node
import json
from dataclasses import dataclass, asdict
class ProjectModel:
    def __init__(self):
        self.nodes: list[Node] = []

    def clear(self):
        self.nodes.clear()

    def to_json(self) -> str:
        return json.dumps([asdict(n) for n in self.nodes], indent=4)

    def from_json(self, text: str):
        self.clear()
        for item in json.loads(text):
            self.nodes.append(Node(**item))
