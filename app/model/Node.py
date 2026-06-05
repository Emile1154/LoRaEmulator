from dataclasses import dataclass
from enum import Enum
import docker
import os
import subprocess
import threading
import time
import traceback
from datetime import timedelta
from meshtastic import config_pb2
from meshtastic.tcp_interface import TCPInterface
from pubsub import pub
from model.meshcore_client import MeshCoreCompanionClient

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

# MeshCore native daemon built from meshcore_firmware/native/ (same Docker image)
MESHCORE_BINARY_PATH = "meshcore_firmware/native/meshcored"

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
    network_type : str  # "meshtastic" | "meshcore"
    noise_std : float

    def __init__(self, x=0, y=0, MAC_address="", local_port=8000, remote_port=8002, web_port=9000, tcp_port=4403,
                 state=None, frequency=0, bandwidth=0, code_rate=0, spreading_factor=0,
                 ldro_enable=False, region="UNSET", slots_count=0, modem_preset="LONG_FAST",
                 network_type="meshtastic", noise_std=2e-6):
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
        self.network_type = network_type
        self.noise_std = noise_std

        self.container_name = f"node_{self.short_mac()}"
        self.start_time = None
        self.interface = None
        self.log_fn = None
        self.packet_received_cb = None  # set by PacketMonitor

    def short_mac(self):
        return self.MAC_address[-4:]

    def logger(self, msg, tag: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{ts}][{tag}][{self.container_name}]({status_text[self.state]}): {msg}"
        print(line)
        if self.log_fn:
            self.log_fn(line)

    def _start_crash_monitor(self, container, on_crash):
        """Stream container logs into a rolling buffer; fire on_crash if container exits unexpectedly."""
        def _monitor():
            log_lines = []
            try:
                for raw in container.logs(stream=True, follow=True):
                    line = raw.decode("utf-8", errors="replace").rstrip()
                    log_lines.append(line)
                    if len(log_lines) > 100:
                        log_lines.pop(0)
            except Exception:
                pass
            if self.state == State.RUNNING:
                self.state = State.ERROR
                if on_crash:
                    on_crash(self, "\n".join(log_lines[-60:]))

        threading.Thread(target=_monitor, daemon=True, name=f"monitor_{self.container_name}").start()

    def enable(self, on_crash=None, on_started=None):
        if self.network_type == "meshcore":
            return self._enable_meshcore(on_crash, on_started)
        return self._enable_meshtastic(on_crash, on_started)

    def _enable_meshtastic(self, on_crash=None, on_started=None):
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
            self._start_crash_monitor(container, on_crash)
            self.open_shell()
            if on_started:
                on_started()
            time.sleep(15)
            self.init_meshtastic_client()
            return 0
        return 0

    def _enable_meshcore(self, on_crash=None, on_started=None):
        client = docker.from_env()
        workspace_path = PROJECT_ROOT

        try:
            client.images.get(f"{IMAGE_NAME}:latest")
        except docker.errors.ImageNotFound:
            self.logger(f"Image {IMAGE_NAME} not found", "INFO")
            dockerfile_path = os.path.join(workspace_path, "docker", "Dockerfile")
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
            self.logger(f"creating MeshCore container: {self.container_name}", "INFO")

            binary_path = os.path.join(workspace_path, MESHCORE_BINARY_PATH)
            if not (os.path.exists(binary_path) and os.access(binary_path, os.X_OK)):
                self.logger("meshcored not found, building inside Docker...", "INFO")

                # Remove stale build container if it exists
                try:
                    client.containers.get("build_meshcored").remove(force=True)
                except docker.errors.NotFound:
                    pass

                build_cmd = "make -C meshcore_firmware/native"
                build_container = client.containers.run(
                    IMAGE_NAME,
                    command=build_cmd, detach=True, name="build_meshcored",
                    network_mode='host',
                    volumes={workspace_path: {'bind': '/home/user/workspace', 'mode': 'rw'}},
                    working_dir='/home/user/workspace',
                )
                exit_code = 1
                try:
                    for line in build_container.logs(stream=True, follow=True):
                        print(line.decode('utf-8').strip())
                    result = build_container.wait()
                    exit_code = result.get('StatusCode', 1)
                finally:
                    try:
                        build_container.remove(force=True)
                    except docker.errors.NotFound:
                        pass

                if exit_code != 0:
                    self.logger(f"meshcored build failed (exit={exit_code})", "ERROR")
                    return 3
                self.logger("meshcored built successfully", "INFO")

            launch_cmd = (
                f"./meshcored"
                f" -p {self.tcp_port}"
                f" -l {self.local_port}"
                f" -r {self.remote_port}"
                f" -h {self.MAC_address}"
            )

            container = client.containers.run(
                IMAGE_NAME,
                command=launch_cmd,
                detach=True,
                name=self.container_name,
                auto_remove=True,
                network_mode='host',
                volumes={workspace_path: {'bind': '/home/user/workspace/', 'mode': 'rw'}},
                working_dir='/home/user/workspace/meshcore_firmware/native',
            )

            self.start_time = time.time()
            self.state = State.RUNNING
            self.logger(f"container {self.container_name} started (pid={container.attrs['State']['Pid']})", "INFO")
            self._start_crash_monitor(container, on_crash)
            self.open_shell()
            if on_started:
                on_started()
            time.sleep(3)
            self.init_meshcore_client()
            return 0
        return 0

    def init_meshtastic_client(self):
        try:
            self.interface = TCPInterface(hostname="localhost", portNumber=self.tcp_port)
        except Exception as e:
            self.logger(f"TCP connect failed on port {self.tcp_port}: {e}", "ERROR")
            self.logger(traceback.format_exc(), "ERROR")
            self.check_container_status()
            return
        
        node = self.interface.localNode
        if node is None:
            self.logger("localNode not available after connect", "ERROR")
            self.interface.close()
            return
        
        self.logger(f"connected on port {self.tcp_port}, configuring radio", "INFO")
        pub.subscribe(self.on_packet_receive, "meshtastic.receive")
        node.setTime()

        lc = node.localConfig
        lc.lora.region = config_pb2.Config.LoRaConfig.RegionCode.RU
        lc.lora.use_preset = True
        lc.lora.modem_preset = config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST
        node.writeConfig("lora")
        time.sleep(2)
        # Interface stays open — it is the permanent packet-receive monitor.

    def init_meshcore_client(self):
        client = MeshCoreCompanionClient(host="localhost", port=self.tcp_port)
        client.on_channel_message = lambda ch, _, text: self.logger(
            f"[ch{ch}] {text}", "MESHCORE"
        )
        client.on_contact_message = lambda sender, _, text: self.logger(
            f"[dm:{sender[:8]}] {text}", "MESHCORE"
        )
        if client.connect():
            self.interface = client
            self.logger(
                f"MeshCore companion connected on port {self.tcp_port} "
                f"(device: {client.device_name or '?'})",
                "INFO",
            )
        else:
            self.logger(f"MeshCore companion failed to connect on port {self.tcp_port}", "ERROR")
            self.check_container_status()
    
    def on_packet_receive(self, packet, interface):
        if interface is not self.interface:
            return
        self.logger(f"new packet received", "INFO")
        if self.packet_received_cb is not None:
            self.packet_received_cb(packet)
    
    def send_message(self, target: 'Node', text: str):
        if self.interface is None:
            self.logger("cannot send message: no active interface", "ERROR")
            return
        target_id = "!" + target.MAC_address.replace(":", "")[4:].lower()
        try:
            self.interface.sendText(text, destinationId=target_id)
            self.logger(f"message {self.MAC_address} -> {target.MAC_address}: {text[:60]}", "INFO")
        except Exception as e:
            self.logger(f"send_message error: {e}", "ERROR")

    def send_ping(self, target: 'Node'):
        if self.interface is None:
            self.logger("cannot send ping: Python API client not connected", "ERROR")
            return

        from meshtastic import portnums_pb2

        target_4bytes = target.MAC_address.replace(':', '')[4:].lower()
        target_node_id = f"!{target_4bytes}"
        # Pattern seen in firmware log when the ACK routing packet arrives back at us
        ack_log_marker = f"Received routing from=0x{target_4bytes}"

        self.logger(f"ping {self.MAC_address} -> {target.MAC_address} ...", "PING")

        ack_event = threading.Event()
        rtt_ref = [None]
        t0_ref = [time.time()]

        def _watch_logs():
            try:
                dc = docker.from_env()
                container = dc.containers.get(self.container_name)
                # since-1 to avoid missing logs on integer-second boundary
                for raw in container.logs(
                    stream=True, follow=True,
                    since=max(0, int(t0_ref[0]) - 1),
                ):
                    if ack_event.is_set():
                        return
                    line = raw.decode("utf-8", errors="replace")
                    if ack_log_marker in line:
                        rtt_ref[0] = (time.time() - t0_ref[0]) * 1000
                        ack_event.set()
                        return
            except Exception as e:
                self.logger(f"log-watch error: {e}", "ERROR")

        try:
            t0_ref[0] = time.time()
            threading.Thread(
                target=_watch_logs, daemon=True,
                name=f"ping_watch_{self.container_name}"
            ).start()
            time.sleep(0.05)  # ensure log watcher is running before send

            self.interface.sendData(
                b"ping",
                destinationId=target_node_id,
                portNum=portnums_pb2.PortNum.TEXT_MESSAGE_APP,
                wantAck=True,
            )

            if ack_event.wait(timeout=30):
                self.logger(
                    f"ping {self.MAC_address} <- {target.MAC_address} RTT={rtt_ref[0]:.0f} ms", "PING"
                )
            else:
                self.logger(
                    f"ping timeout: {self.MAC_address} -> {target.MAC_address} (no ACK in 30 s)", "PING"
                )
        except Exception as e:
            self.logger(f"ping {self.MAC_address} -> {target.MAC_address} error : {e}", "ERROR")
        finally:
            ack_event.set()  # stop log watcher

    def connect_api_client(self):
        if self.network_type != "meshtastic":
            return
        if self.interface is not None:
            if getattr(self.interface, 'isConnected', False):
                self.logger("Python API client already connected", "INFO")
                return
            # stale closed reference — clear it and reconnect
            self.interface = None
        for attempt in range(3):
            try:
                self.interface = TCPInterface(
                    hostname="localhost",
                    portNumber=self.tcp_port,
                    timeout=60,
                )
                self.logger(f"Python API client connected on port {self.tcp_port}", "INFO")
                return
            except Exception as e:
                self.interface = None
                if attempt < 2:
                    self.logger(f"connect attempt {attempt + 1}/3 failed: {e} — retrying in 5 s", "WARN")
                    time.sleep(5)
                else:
                    self.logger(f"Python API client connect failed: {e}", "ERROR")

    def disconnect_api_client(self):
        if self.interface is None:
            self.logger("Python API client is not connected", "INFO")
            return
        try:
            self.interface.close()
            self.interface = None
            self.logger("Python API client disconnected", "INFO")
        except Exception as e:
            self.logger(f"Python API client disconnect error: {e}", "ERROR")
            self.interface = None

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
        