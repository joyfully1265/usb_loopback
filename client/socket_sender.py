import socket
import struct


class SocketSender:
    """Handles TCP communication with the USB HID server."""

    def __init__(self, host="127.0.0.1", port=9999):
        self.host = host
        self.port = port
        self.socket = None
        self.connect()

    def connect(self):
        """Establish a connection to the server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            self.socket = None

    def send(self, msg_type, payload):
        """Send a message to the server.

        Args:
            msg_type: 0 for keyboard, 1 for mouse.
            payload: bytes object containing the HID report.
        """
        if self.socket is None:
            self.connect()
            if self.socket is None:
                print("Cannot send: not connected to server")
                return False

        try:
            # Message format: 1 byte type + payload
            message = struct.pack("B", msg_type) + payload
            self.socket.sendall(message)
            return True
        except Exception as e:
            print(f"Failed to send message: {e}")
            self.socket = None
            return False

    def close(self):
        """Close the socket."""
        if self.socket:
            self.socket.close()
            self.socket = None
