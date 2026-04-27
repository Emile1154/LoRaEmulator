# meshtastic_tcp_example.py
import meshtastic
from meshtastic import mesh_pb2, config_pb2   # Important: import config_pb2 for enums
from pubsub import pub
from meshtastic.tcp_interface import TCPInterface

HOST = "localhost"   # replace with your TCP bridge host
PORT = 4403          # replace with your TCP bridge port

def onReceive(packet, interface):
    print(f"Received: {packet}")
    # Example: Access text message content
    if 'decoded' in packet and packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
        print(f"Message text: {packet['decoded']['text']}")

# 2. Define a callback for when the connection is established
def onConnection(interface, topic=pub.AUTO_TOPIC):
    print("Connected to radio via TCP!")

    node = interface.localNode
    lc = node.localConfig

    # Set LoRa region (e.g., EU_868, US, EU_433, etc.)
    lc.lora.region = config_pb2.Config.LoRaConfig.RegionCode.EU_868

    # Enable preset mode and select a modem preset
    lc.lora.use_preset = True
    lc.lora.modem_preset = config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST

    # Write the lora config to the device
    node.writeConfig("lora")
    print(f"LoRa config set: region={lc.lora.region}, modem_preset={lc.lora.modem_preset}")



pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")
# Create a TCP transport and client
interface = TCPInterface(hostname=HOST, portNumber=PORT)


 
try:
    while True:
        pass
except KeyboardInterrupt:
    interface.close()