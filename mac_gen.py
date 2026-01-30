import random

def generate_mac_address():
    # Generate a random MAC address
    mac = [random.randint(0x00, 0xFF) for _ in range(6)]
    # Format into a continuous hexadecimal string
    mac_address = ''.join(f'{byte:02x}' for byte in mac)
    return mac_address.upper()  # Convert to uppercase for standard formatting

if __name__ == '__main__':
    mac_address = generate_mac_address()
    print(f"Generated MAC Address: {mac_address}")