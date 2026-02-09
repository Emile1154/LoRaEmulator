from dataclasses import dataclass, asdict
from enum import Enum
import docker

class State(Enum):
    CREATED  = 1
    STARTING = 2
    RUNNING  = 3
    ERROR    = 4
    STOPPED  = 5

status_text = {
    State.CREATED:  "CREATED",
    State.STARTING:"STARTING",
    State.RUNNING: "RUNNING",
    State.STOPPED: "STOPPED",
    State.ERROR:   "ERROR",
}

IMAGE_NAME = "meshtastic-firmware-dev"
MESHTASTIC_ABSOLUTE_PATH = "/home/user/workspace/meshtastic_firmware/.pio/build/native_virtual/meshtasticd"
@dataclass
class Node:
    web_port: int
    local_port: int
    remote_port: int
    state : State
    x: float
    y: float

    MAC_address: str

    frequency : int
    bandwidth : int
    code_rate : int
    spreading_factor : int
    ldro_enable : bool

    def __init__(self, x, y, mac):
        self.local_port = 8000
        self.remote_port = 8002
        self.web_port = 9000

        self.x = x
        self.y = y 
        self.MAC_address = mac
        
        self.state = State.CREATED

        self.frequency = 0
        self.bandwidth = 0
        self.code_rate = 0
        self.spreading_factor = 0
        self.ldro_enable = 0
        
    def short_mac(self):
        return self.MAC_address[-4:]


    def logger(self, msg, tag: str):
        print(f"[{tag}][{self.short_mac}]({status_text[self.state]}): {msg}")

    def enable(self) -> str:
        # open docker conatiner
        client = docker.from_env()
        container_name = f"node_{self.local_port}"
         
        try:
            container = client.containers.get(container_name)
            if container.status == "running":
                self.logger(f"container {container_name} is already running.", "INFO")
                return container.status
        except docker.errors.NotFound:
            # create container
            self.logger(f"creating a new container: {container_name}", "INFO")

            # -s -v -l "$1" -r "$2" -w "$3" -h "$MAC_ADDR
            launch_daemon = f".{MESHTASTIC_ABSOLUTE_PATH} -s -v -l {self.local_port} -r {self.remote_port} -w {self.web_port} -h {self.MAC_address}" 
            container = client.containers.run(IMAGE_NAME, 
                                              command=launch_daemon, detach=True,name=container_name, 
                                              ports={self.local_port: self.remote_port, self.web_port: self.web_port})
            self.logger(f"container {container_name} started", "INFO")

    def shutdown(self):
        client = docker.from_env()
        container_name = f"node_{self.local_port}"

        try:
            container = client.containers.get(container_name)
            container.stop()
            container.remove()
            self.logger(f"container {container_name} is stopped and removed", "INFO")
        except:
            self.logger(f"container {container_name} doesn't exist.", "INFO")
        