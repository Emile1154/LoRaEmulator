from dataclasses import dataclass, asdict

@dataclass
class Node:
    web_port: int
    local_port: int
    remote_port: int
    x: float
    y: float