from dataclasses import dataclass, asdict
from enum import Enum

class State(Enum):
    CREATED  = 1
    STARTING = 2
    RUNNING  = 3
    ERROR    = 4
    STOPPED  = 5

@dataclass
class Node:
    web_port: int
    local_port: int
    remote_port: int
    state : State
    x: float
    y: float