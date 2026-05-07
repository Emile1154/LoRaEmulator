from dataclasses import dataclass, asdict
from enum import Enum
import docker
import os
import subprocess
import time
import traceback
from datetime import timedelta
from meshtastic import mesh_pb2, config_pb2
from pubsub import pub
from meshtastic.tcp_interface import TCPInterface

class State(Enum):
    CREATED  = 1
    STARTING = 2
    RUNNING  = 3
    ERROR    = 4
    STOPPING = 5
    STOPPED  = 6

status_text = {
    State.CREATED:  "CREATED",
    State.STARTING:"STARTING",
    State.RUNNING: "RUNNING",
    State.STOPPING: "STOPPING",
    State.STOPPED: "STOPPED",
    State.ERROR:   "ERROR",
}

IMAGE_NAME = "meshtastic-firmware-dev"
MESHTASTIC_ABSOLUTE_PATH = "./meshtasticd"

# Resolve absolute project root (parent of app/ directory)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@dataclass
class Node:
    web_port: int
    local_port: int
    remote_port: int
    tcp_port: int
    state : State
    x: float
    y: float

    MAC_address: str

    frequency : int
    bandwidth : int
    code_rate : int
    spreading_factor : int
    ldro_enable : bool
    region : str
    slots_count : int
    modem_preset : str

    def __init__(self, x=0, y=0, MAC_address="", local_port=8000, remote_port=8002, web_port=9000, tcp_port=4403,
                 state=None, frequency=0, bandwidth=0, code_rate=0, spreading_factor=0,
                 ldro_enable=False, region="UNSET", slots_count=0, modem_preset="LONG_FAST"):
        self.local_port = local_port
        self.remote_port = remote_port
        self.web_port = web_port
        self.tcp_port = tcp_port

        self.x = x
        self.y = y
        self.MAC_address = MAC_address

        self.state = state if state is not None else State.CREATED

        self.frequency = frequency
        self.bandwidth = bandwidth
        self.code_rate = code_rate
        self.spreading_factor = spreading_factor
        self.ldro_enable = ldro_enable
        self.region = region
        self.slots_count = slots_count
        self.modem_preset = modem_preset

        self.container_name = f"node_{self.short_mac()}"
        self.start_time = None
        self.interface = None

    def short_mac(self):
        return self.MAC_address[-4:]

    def logger(self, msg, tag: str):
        print(f"[{tag}][{self.container_name}]({status_text[self.state]}): {msg}")

    def enable(self):
        client = docker.from_env()
        workspace_path = PROJECT_ROOT

        try:
            client.images.get(f"{IMAGE_NAME}:latest")
        except docker.errors.ImageNotFound:
            self.logger(f"Image {IMAGE_NAME} not found", "INFO")
            # Build Docker image
            dockerfile_path = os.path.join(workspace_path,"docker","Dockerfile")

            self.logger("Building Docker image...", "INFO")

            build_image_cmd = ["docker", "build", "-t", IMAGE_NAME, "-f", dockerfile_path]
            image_result = subprocess.run(build_image_cmd, capture_output=True, text=True)
            if image_result.returncode != 0:
                self.logger(f"Docker image build failed: {image_result.stderr}", "ERROR")
                return 1
            self.logger("Docker image built successfully", "INFO")

        try:
            container = client.containers.get(self.container_name)
            if container.status == "running":
                self.logger(f"container {self.container_name} is already running.", "INFO")
                return 2
        except docker.errors.NotFound:
            # create container
            self.logger(f"creating a new container: {self.container_name}", "INFO")

            # Check if firmware binary exists and is executable
            firmware_path = f"{workspace_path}/meshtastic_firmware/.pio/build/native_virtual/meshtasticd"
            if not (os.path.exists(firmware_path) and os.access(firmware_path, os.X_OK)):
                self.logger(f"meshtasticd not found, building project...", "INFO")
                
                # Build meshtasticd
                self.logger("Running build in Docker container...", "INFO")
                build_cmd = "pio run -e native_virtual"
                container = client.containers.run(IMAGE_NAME,
                    command=build_cmd, detach=True, name="build_meshtasicd",
                    auto_remove=True, network_mode='host',
                    volumes={f'{workspace_path}' : {'bind': '/home/user/workspace', 'mode': 'rw'} },
                    working_dir='/home/user/workspace/meshtastic_firmware',
                )
                for line in container.logs(stream=True, follow=True):
                    print(line.decode('utf-8').strip())

                container.wait()
                exit_code = container.attrs['State']['ExitCode']
                if exit_code != 0:
                    # Get the logs if the build failed
                    build_result = container.logs()
                    self.logger(f"Build failed: {build_result.decode('utf-8')}", "ERROR")
                    return 3
                self.logger("Build completed successfully", "INFO")
            
            # Run meshtasticd inside Docker container
            # -s -v -l "$1" -r "$2" -w "$3" -h "$MAC_ADDR
            launch_daemon = f"./meshtasticd -s -v -p {self.tcp_port} -l {self.local_port} -r {self.remote_port} -w {self.web_port} -h {self.MAC_address}"
            
            # Warn if web root is missing (hard-coded in firmware to /home/user/workspace/web)
            web_root = os.path.join(workspace_path, "web")
            if not os.path.isdir(web_root):
                self.logger(f"WARNING: web root not found at {web_root}. Web UI will return 404.", "WARN")
            
            container = client.containers.run(IMAGE_NAME,
                                              command=launch_daemon, detach=True, name=self.container_name,
                                              auto_remove=True, network_mode='host',
                                              volumes={f'{workspace_path}': {'bind': '/home/user/workspace/', 'mode': 'rw'}},
                                              working_dir='/home/user/workspace/meshtastic_firmware/.pio/build/native_virtual',
                                            )

            self.start_time = time.time()
            self.state = State.RUNNING
            self.logger(f"container {self.container_name} started (pid={container.attrs['State']['Pid']})", "INFO")
            self.open_shell()
            time.sleep(8)
            self.init_meshtastic_client()
            return 0
        return 0

    def init_meshtastic_client(self):
        try:
            self.interface = TCPInterface(hostname="localhost", portNumber=self.tcp_port)
            pub.subscribe(self.onConnection, "meshtastic.connection.established")
            self.logger(f"meshtastic TCP client initiated on port {self.tcp_port}", "INFO")
        except Exception as e:
            self.logger(f"meshtastic TCP client failed to connect on port {self.tcp_port}: {e}", "ERROR")
            self.logger(traceback.format_exc(), "ERROR")
            self.check_container_status()

    def onConnection(self, interface, **kwargs):
        self.logger(f"connected to radio via TCP for container: {self.container_name}", "INFO")
        node = self.interface.localNode
        lc = node.localConfig
        lc.lora.region = config_pb2.Config.LoRaConfig.RegionCode.RU
        lc.lora.use_preset = True
        lc.lora.modem_preset = config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST
        node.writeConfig("lora")

    def check_container_status(self):
        client = docker.from_env()
        try:
            container = client.containers.get(self.container_name)
            status = container.status
            attrs = container.attrs
            state = attrs.get('State', {})

            runtime_sec = 0.0
            if self.start_time:
                runtime_sec = time.time() - self.start_time

            self.logger(
                f"container status={status} runtime={timedelta(seconds=int(runtime_sec))} "
                f"started_at={state.get('StartedAt','?')} pid={state.get('Pid','?')}",
                "INFO"
            )

            if status != "running":
                exit_code = state.get('ExitCode', '?')
                error_msg = state.get('Error', '')
                self.logger(
                    f"container NOT RUNNING: exit_code={exit_code} error='{error_msg}'",
                    "ERROR"
                )
                logs = container.logs(tail=50)
                if logs:
                    self.logger(f"last container logs:\n{logs.decode('utf-8', errors='replace').strip()}", "ERROR")
                self.state = State.ERROR
                return False
            return True
        except docker.errors.NotFound:
            self.logger("container not found during status check", "ERROR")
            self.state = State.ERROR
            return False
        except Exception as e:
            self.logger(f"error checking container status: {e}", "ERROR")
            return False

    def open_shell(self):
        """Open an xterm showing live logs of the running daemon."""
        client = docker.from_env()
        try:
            container = client.containers.get(self.container_name)
            if container.status != "running":
                self.logger(f"container {self.container_name} is not running", "ERROR")
                return 1
            
            # Open xterm following container logs
            cmd = [
                "xterm",
                "-fa", "Monospace",
                "-fs", "10",
                "-T", f"Logs: {self.container_name}",
                "-e", f"docker logs -f {self.container_name}"
            ]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.logger(f"opened log viewer for container {self.container_name}", "INFO")
            return 0
        except docker.errors.NotFound:
            self.logger(f"container {self.container_name} doesn't exist", "ERROR")
            return 1
        except Exception as e:
            self.logger(f"failed to open log viewer: {e}", "ERROR")
            return 1
        
    def open_shell_setup(self):
        """Open an xterm showing live logs of the running daemon."""
        client = docker.from_env()
        try:
            container = client.containers.get(self.container_name)
            if container.status != "running":
                self.logger(f"container {self.container_name} is not running", "ERROR")
                return 1
            
            # Open xterm following container logs
            cmd = [
                "xterm",
                "-fa", "Monospace",
                "-fs", "10",
                "-T", f"Shell: {self.container_name}",
                "-e", f"docker exec -it {self.container_name} /bin/bash"
            ]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.logger(f"opened log viewer for container {self.container_name}", "INFO")
            return 0
        except docker.errors.NotFound:
            self.logger(f"container {self.container_name} doesn't exist", "ERROR")
            return 1
        except Exception as e:
            self.logger(f"failed to open log viewer: {e}", "ERROR")
            return 1
        # Open xterm with docker exec
            

    def shutdown(self):
        client = docker.from_env()
        runtime_sec = 0.0
        if self.start_time:
            runtime_sec = time.time() - self.start_time

        try:
            container = client.containers.get(self.container_name)
            status_before = container.status
            state_before = container.attrs.get('State', {})
            exit_code_before = state_before.get('ExitCode', '?')

            container.stop()
            container.remove(force=True)

            self.state = State.STOPPED
            self.logger(
                f"container stopped and removed (runtime={timedelta(seconds=int(runtime_sec))}, "
                f"status_before={status_before}, exit_code_before={exit_code_before})",
                "INFO"
            )
        except docker.errors.NotFound:
            self.logger(
                f"container not found at shutdown (runtime={timedelta(seconds=int(runtime_sec))})",
                "INFO"
            )
        except Exception as e:
            self.logger(
                f"error stopping container after runtime={timedelta(seconds=int(runtime_sec))}: {e}",
                "ERROR"
            )
            self.logger(traceback.format_exc(), "ERROR")

        if self.interface:
            try:
                self.interface.close()
                self.logger("meshtastic TCP client closed", "INFO")
            except Exception as e:
                self.logger(f"error closing meshtastic client: {e}", "WARN")

        return 0
        