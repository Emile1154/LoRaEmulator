# LoRa Emulator

A emulation platform for LoRa mesh networks using Meshtastic firmware. This project provides environment for emulate multiple LoRa nodes with SDR, managing their configuration, and testing mesh network behavior.

## Overview

LoRa Emulator is a comprehensive tool for:
- **Visual Node Management**: Place, configure, and manage virtual LoRa nodes on a 2D canvas
- **Docker-based Emulation**: Each node runs in its own isolated Docker container with real Meshtastic firmware
- **Physical Level Emulation**: Emulate LoRa channel by FutureSDR 
- **Network Simulation**: Test LoRa mesh networking without real devices
- **Project Management**: Save and load network configurations

## Architecture

The project consists of several integrated components:

![LoRa Emulator Architecture](image/README/image.png)

## Features

### Node Management
- **Visual Placement**: Drag and drop nodes on an infinite 2D canvas
- **Node States**: Visual indication of node status (Created, Starting, Running, Stopped, Error)
- **Configuration**: Per-node settings for:
  - MAC address (auto-generated)
  - Network ports (local, remote, web)
  - LoRa parameters (frequency, bandwidth, spreading factor, code rate)
  - Region settings and modem presets

### Emulation Control
- **Launch All**: Start all configured nodes simultaneously
- **Shutdown All**: Gracefully stop all running nodes
- **Individual Control**: Start/stop nodes independently via context menu
- **Auto-cleanup**: Containers are automatically removed on shutdown

### Project Management
- **Save/Load**: Persist network configurations to JSON files
- **New Project**: Clear canvas and start fresh

## Prerequisites

- **Docker**: For running node containers
- **Python 3.10+**: For the GUI application
- **Rust** (optional): For building LoRaSDR components
- **PlatformIO** (optional): For building meshtastic firmware

## Installation

1. **Clone the repository with submodules**:
   ```bash
   git clone --recursive https://github.com/Emile1154/LoRaEmulator.git
   cd LoRaEmulator
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the GUI Application

```bash
cd app
python main.py
```

### Creating a Network

1. **Add Nodes**: Right-click on the canvas to create new nodes
2. **Configure**: Double-click a node or use "Edit" from context menu
3. **Position**: Drag nodes to arrange your network topology
4. **Launch**: Use "Run → Launch All Devices" or start nodes individually

### Context Menu Options

Right-click on any node to access:
- **Edit**: Modify node configuration
- **Delete**: Remove node from project
- **Enable Device**: Start the node container
- **Disable Device**: Stop the node container
- **Open Web Interface**: Access node's web UI (when running)
- **Open Terminal**: Access node's CLI (when running)

### Node States

| State    | Color  | Description                          |
|----------|--------|--------------------------------------|
| CREATED  | Gray   | Node defined but not started         |
| STARTING | Yellow | Container is launching               |
| RUNNING  | Green  | Node is active and operational       |
| STOPPING | Yellow | Container is shutting down           |
| STOPPED  | Blue   | Node was stopped by user             |
| ERROR    | Red    | Failed to start or crashed           |

## Configuration

### Node Parameters

Each node can be configured with:

- **Network Ports**:
  - Local port: For node communication
  - Remote port: For mesh networking
  - Web port: For HTTP interface access

- **LoRa Settings**:
  - Frequency: Operating frequency in Hz
  - Bandwidth: Signal bandwidth
  - Spreading Factor: SF7-SF12
  - Code Rate: Error correction (4/5, 4/6, 4/7, 4/8)
  - LDRO: Low data rate optimization

- **Mesh Settings**:
  - Region: Regulatory region (EU, US, etc.)
  - Modem Preset: Predefined configuration sets


## Submodules

This project includes several git submodules:

### [meshtastic_firmware](https://github.com/Emile1154/firmware)
Official Meshtastic firmware adapted for native virtual environment. Provides the `meshtasticd` daemon that runs inside each node container.

### [LoRaSDR](https://github.com/Emile1154/LoRaSDR.git)
Rust-based Software Defined LoRa transceiver. Implements:
- LoRa modulation/demodulation
- Frame synchronization
- Channel modeling with AWGN
- Packet forwarding

### [FutureSDR](https://github.com/FutureSDR/FutureSDR.git)
SDR framework providing the runtime and building blocks for LoRaSDR.

## Development

### Building Meshtastic Firmware

The firmware is built automatically on first node launch, but can be built manually:

```bash
cd meshtastic_firmware
pio run -e native_virtual
```

### Running Individual Nodes

For testing without the GUI:

```bash
./run_node.sh
```

Then inside the container:
```bash
./meshtasticd -s -v -l 8000 -r 8002 -w 9000 -h <MAC_ADDRESS>
```

### Project File Format

Projects are saved as JSON arrays of node configurations:

```json
[
  {
    "web_port": 9000,
    "local_port": 8000,
    "remote_port": 8002,
    "state": 3,
    "x": 100.0,
    "y": 200.0,
    "MAC_address": "A1B2C3D4E5F6",
    "frequency": 868000000,
    "bandwidth": 125000,
    "code_rate": 4,
    "spreading_factor": 7,
    "ldro_enable": false,
    "region": "EU868",
    "slots_count": 0,
    "modem_preset": "LONG_FAST"
  }
]
```

## License

- **LoRaSDR**: GNU GPL v3 (derived from gr-lora_sdr)
- **Meshtastic Firmware**: GPL v3
- **Application Code**: See repository for specific licensing

## Acknowledgments

- [Meshtastic](https://meshtastic.org/) project for the mesh networking firmware
- [FutureSDR](https://github.com/FutureSDR/FutureSDR) team for the SDR framework
- [gr-lora_sdr](https://github.com/tapparelj/gr-lora_sdr) by Tapparel et al. for LoRa implementation

## Troubleshooting

### Firmware Build Failures
Check that all submodules are initialized:
```bash
git submodule update --init --recursive
```

### Port Conflicts
Ensure the configured ports (default 8000, 8002, 9000) are not in use by other applications.
