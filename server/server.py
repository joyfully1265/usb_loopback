#!/usr/bin/env python3
"""
USB HID Server for USB Loopback project.

Listens for TCP connections from clients and writes HID reports to
/dev/hidg0 (keyboard) and /dev/hidg1 (mouse).
"""

import socket
import struct
import threading
import errno
import os
import datetime

# HID Keyboard scan code to name mapping (partial, most common keys)
KEYCODE_NAMES = {
    0x00: "NONE",
    0x04: "A",
    0x05: "B",
    0x06: "C",
    0x07: "D",
    0x08: "E",
    0x09: "F",
    0x0A: "G",
    0x0B: "H",
    0x0C: "I",
    0x0D: "J",
    0x0E: "K",
    0x0F: "L",
    0x10: "M",
    0x11: "N",
    0x12: "O",
    0x13: "P",
    0x14: "Q",
    0x15: "R",
    0x16: "S",
    0x17: "T",
    0x18: "U",
    0x19: "V",
    0x1A: "W",
    0x1B: "X",
    0x1C: "Y",
    0x1D: "Z",
    0x1E: "1",
    0x1F: "2",
    0x20: "3",
    0x21: "4",
    0x22: "5",
    0x23: "6",
    0x24: "7",
    0x25: "8",
    0x26: "9",
    0x27: "0",
    0x28: "ENTER",
    0x29: "ESC",
    0x2A: "BACKSPACE",
    0x2B: "TAB",
    0x2C: "SPACE",
    0x2D: "MINUS",
    0x2E: "EQUAL",
    0x2F: "LBRACKET",
    0x30: "RBRACKET",
    0x31: "BACKSLASH",
    0x33: "SEMICOLON",
    0x34: "QUOTE",
    0x35: "GRAVE",
    0x36: "COMMA",
    0x37: "PERIOD",
    0x38: "SLASH",
    0x39: "CAPSLOCK",
    0x3A: "F1",
    0x3B: "F2",
    0x3C: "F3",
    0x3D: "F4",
    0x3E: "F5",
    0x3F: "F6",
    0x40: "F7",
    0x41: "F8",
    0x42: "F9",
    0x43: "F10",
    0x44: "F11",
    0x45: "F12",
    0x46: "PRINTSCREEN",
    0x47: "SCROLLLOCK",
    0x48: "PAUSE",
    0x49: "INSERT",
    0x4A: "HOME",
    0x4B: "PAGEUP",
    0x4C: "DELETE",
    0x4D: "END",
    0x4E: "PAGEDOWN",
    0x4F: "RIGHT",
    0x50: "LEFT",
    0x51: "DOWN",
    0x52: "UP",
    0x53: "NUMLOCK",
    0x54: "KP_SLASH",
    0x55: "KP_ASTERISK",
    0x56: "KP_MINUS",
    0x57: "KP_PLUS",
    0x58: "KP_ENTER",
    0x59: "KP1",
    0x5A: "KP2",
    0x5B: "KP3",
    0x5C: "KP4",
    0x5D: "KP5",
    0x5E: "KP6",
    0x5F: "KP7",
    0x60: "KP8",
    0x61: "KP9",
    0x62: "KP0",
    0x63: "KP_PERIOD",
    # Modifier keys
    0xE0: "LCTRL",
    0xE1: "LSHIFT",
    0xE2: "LALT",
    0xE3: "LGUI",
    0xE4: "RCTRL",
    0xE5: "RSHIFT",
    0xE6: "RALT",
    0xE7: "RGUI",
}

# Modifier bit positions
MODIFIER_KEYS = {
    0xE0: 0,
    0xE1: 1,
    0xE2: 2,
    0xE3: 3,
    0xE4: 4,
    0xE5: 5,
    0xE6: 6,
    0xE7: 7,
}

MODIFIER_NAMES = {
    0: "LCTRL",
    1: "LSHIFT",
    2: "LALT",
    3: "LGUI",
    4: "RCTRL",
    5: "RSHIFT",
    6: "RALT",
    7: "RGUI",
}


def _debug_keycode(keycode):
    """Return human-readable name for a HID keycode."""
    return KEYCODE_NAMES.get(keycode, f"0x{keycode:02X}")


def _decode_keyboard_report(report):
    """Decode an 8-byte HID keyboard report into a human-readable string.

    Report format: [modifier, reserved, keycode0, keycode1, keycode2, keycode3, keycode4, keycode5]
    """
    modifier = report[0]
    keycodes = [report[i] for i in range(2, 8)]

    parts = []

    # Decode modifier bits
    active_mods = []
    for bit in range(8):
        if modifier & (1 << bit):
            active_mods.append(MODIFIER_NAMES.get(bit, f"MOD{bit}"))
    if active_mods:
        parts.append(" + ".join(active_mods))

    # Decode keycodes
    active_keys = []
    for kc in keycodes:
        if kc != 0:
            active_keys.append(_debug_keycode(kc))
    if active_keys:
        parts.extend(active_keys)

    if not parts:
        return "KEY_RELEASE (all keys up)"
    return " + ".join(parts)


def _decode_mouse_report(report):
    """Decode a 4-byte HID mouse report into a human-readable string.

    Report format: [buttons, x, y, wheel]
    """
    buttons = report[0]
    x = struct.unpack("b", bytes([report[1]]))[0]
    y = struct.unpack("b", bytes([report[2]]))[0]

    parts = []

    btn_names = []
    if buttons & 0x01:
        btn_names.append("LEFT")
    if buttons & 0x02:
        btn_names.append("RIGHT")
    if buttons & 0x04:
        btn_names.append("MIDDLE")
    if buttons & 0x08:
        btn_names.append("BUTTON4")
    if buttons & 0x10:
        btn_names.append("BUTTON5")
    if btn_names:
        parts.append("Buttons: " + "+".join(btn_names))

    if x != 0 or y != 0:
        parts.append(f"Move: dx={x}, dy={y}")

    if not parts:
        return "Mouse: no change"
    return ", ".join(parts)


class HIDServer:
    def __init__(
        self,
        host="127.0.0.1",
        port=9999,
        keyboard_device="/dev/hidg0",
        mouse_device="/dev/hidg1",
    ):
        self.host = host
        self.port = port
        self.keyboard_device = keyboard_device
        self.mouse_device = mouse_device
        self.server_socket = None
        self.running = False
        self.keyboard_fd = None
        self.mouse_fd = None
        self.ready_event = threading.Event()
        self._lock = threading.Lock()

    def start(self):
        """Start the HID server."""
        try:
            # Open HID devices
            flags = os.O_WRONLY
            if hasattr(os, "O_NONBLOCK"):
                flags |= os.O_NONBLOCK
            self.keyboard_fd = os.open(self.keyboard_device, flags)
            self.mouse_fd = os.open(self.mouse_device, flags)
            print(f"Opened HID devices: {self.keyboard_device}, {self.mouse_device}")
        except Exception as e:
            print(f"Failed to open HID devices: {e}")
            return False

        try:
            # Create TCP server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            self.ready_event.set()
            print(f"HID Server listening on {self.host}:{self.port}")

            # Accept connections in a loop
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    print(f"Accepted connection from {addr}")
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client, args=(client_socket, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.error as e:
                    if self.running:
                        print(f"Socket error: {e}")
                    break
        except Exception as e:
            print(f"Server error: {e}")
            return False
        finally:
            self.stop()
        return True

    def stop(self):
        """Stop the HID server."""
        self.running = False
        with self._lock:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
            if self.keyboard_fd is not None:
                os.close(self.keyboard_fd)
                self.keyboard_fd = None
            if self.mouse_fd is not None:
                os.close(self.mouse_fd)
                self.mouse_fd = None
        print("HID Server stopped")

    def handle_client(self, client_socket, addr):
        """Handle communication with a connected client."""
        print(f"Handling client {addr}")
        try:
            while self.running:
                # Receive message: 1 byte type + payload
                header = self._recv_exact(client_socket, 1)
                if not header:
                    break

                msg_type = struct.unpack("B", header)[0]

                if msg_type == 0:  # Keyboard report
                    payload = self._recv_exact(
                        client_socket, 8
                    )  # 8-byte keyboard report
                    if payload and len(payload) == 8:
                        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        decoded = _decode_keyboard_report(payload)
                        raw_hex = " ".join(f"{b:02X}" for b in payload)
                        print(f"[{ts}] [KEYBOARD] {decoded}  (raw: {raw_hex})")
                        self._write_hid_report(self.keyboard_fd, payload)
                elif msg_type == 1:  # Mouse report (relative)
                    payload = self._recv_exact(
                        client_socket, 4
                    )  # 4-byte relative mouse report
                    if payload and len(payload) == 4:
                        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        decoded = _decode_mouse_report(payload)
                        raw_hex = " ".join(f"{b:02X}" for b in payload)
                        print(f"[{ts}] [MOUSE]    {decoded}  (raw: {raw_hex})")
                        self._write_hid_report(self.mouse_fd, payload)
                elif msg_type == 2:  # Mouse report (absolute)
                    payload = self._recv_exact(
                        client_socket, 6
                    )  # 6-byte absolute mouse report
                    if payload and len(payload) == 6:
                        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        buttons = payload[0]
                        abs_x = payload[1] | (payload[2] << 8)
                        abs_y = payload[3] | (payload[4] << 8)
                        wheel = struct.unpack("b", bytes([payload[5]]))[0]
                        raw_hex = " ".join(f"{b:02X}" for b in payload)
                        print(
                            f"[{ts}] [MOUSE_ABS] buttons={buttons} x={abs_x} y={abs_y} wheel={wheel}  (raw: {raw_hex})"
                        )
                        self._write_hid_report(self.mouse_fd, payload)
                else:
                    print(f"Unknown message type: {msg_type}")
                    break
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            client_socket.close()
            print(f"Connection closed for {addr}")

    def _recv_exact(self, sock, length):
        """Receive exactly 'length' bytes from socket."""
        data = b""
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _write_hid_report(self, fd, report):
        """Write HID report to file descriptor."""
        with self._lock:
            if fd is None:
                return
            try:
                os.write(fd, report)
                # os.fsync(fd)  # Flush to disk so tests can read it immediately
            except OSError as e:
                # Ignore EAGAIN/EWOULDBLOCK errors (non-blocking write would block)
                if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    print(f"Error writing HID report: {e}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="USB HID Server for USB Loopback")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9999, help="Port to listen on")
    args = parser.parse_args()

    server = HIDServer(args.host, args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
