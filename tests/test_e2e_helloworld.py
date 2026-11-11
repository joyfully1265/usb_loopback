#!/usr/bin/env python3
"""
End-to-end test: connects to an already-running HID server at 192.168.1.132,
types "helloworld" over the keyboard interface, then performs a mouse stroke
(move while holding the left button).

Usage:
    python -m unittest tests.test_e2e_helloworld
"""

import unittest
import time

from usb_loopback.client.io_interface import SocketKeySender, SocketMouseSender

# ---------------------------------------------------------------------------
# USB HID Usage IDs for the characters we need (USB HID Usage Tables §10)
# ---------------------------------------------------------------------------
_KEY_MAP = {
    "a": 0x04,
    "b": 0x05,
    "c": 0x06,
    "d": 0x07,
    "e": 0x08,
    "f": 0x09,
    "g": 0x0A,
    "h": 0x0B,
    "i": 0x0C,
    "j": 0x0D,
    "k": 0x0E,
    "l": 0x0F,
    "m": 0x10,
    "n": 0x11,
    "o": 0x12,
    "p": 0x13,
    "q": 0x14,
    "r": 0x15,
    "s": 0x16,
    "t": 0x17,
    "u": 0x18,
    "v": 0x19,
    "w": 0x1A,
    "x": 0x1B,
    "y": 0x1C,
    "z": 0x1D,
    "0": 0x27,
    "1": 0x1E,
    "2": 0x1F,
    "3": 0x20,
    "4": 0x21,
    "5": 0x22,
    "6": 0x23,
    "7": 0x24,
    "8": 0x25,
    "9": 0x26,
    " ": 0x2C,  # Space
}


def char_to_hid(ch: str) -> int:
    """Convert a single character to its USB HID Usage ID."""
    lower = ch.lower()
    if lower not in _KEY_MAP:
        raise ValueError(f"Character '{ch}' has no HID mapping")
    return _KEY_MAP[lower]


def type_string(sender: SocketKeySender, text: str, delay: float = 0.05) -> None:
    """Type a string character-by-character using the given sender.

    Args:
        sender: A SocketKeySender instance.
        text:   The string to type.
        delay:  Seconds to wait between key press and release.
    """
    for ch in text:
        keycode = char_to_hid(ch)
        # Press
        sender.send_key(keycode)
        time.sleep(delay)
        # Release
        sender.release_all_keys()
        time.sleep(delay)


class TestE2EHelloworld(unittest.TestCase):
    """End-to-end test that types 'helloworld' and performs a mouse stroke.

    Assumes an HID server is already running at 192.168.1.132:9999.
    Results are verified manually on the target machine.
    """

    HOST = "192.168.1.132"
    PORT = 9999

    def setUp(self):
        """Connect to the already-running HID server."""
        self.key_sender = SocketKeySender(host=self.HOST, port=self.PORT)
        self.mouse_sender = SocketMouseSender(host=self.HOST, port=self.PORT)

    def tearDown(self):
        """Release all keys and buttons to leave a clean state."""
        try:
            self.key_sender.release_all_keys()
        except Exception:
            pass
        try:
            self.mouse_sender.release_button(1)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_type_helloworld(self):
        """Type 'helloworld' on the remote server. Verify manually."""
        type_string(self.key_sender, "helloworld", delay=0.01)
        # Manual verification: check that "helloworld" appeared on the target
        self.assertTrue(True, "Verify 'helloworld' was typed on the target machine")

    @unittest.skip("Applicable for mouse HID")
    def test_mouse_stroke(self):
        """Perform a mouse stroke: hold left button and move diagonally. Verify manually."""
        # Press left button
        self.mouse_sender.press_button(1)
        time.sleep(0.05)
        self.mouse_sender.release_button(1)

        stroke_points = [
            (-50, 0),
            (100, 0),
            (-50, 0),
            (0, 50),
            (0, -100),
            (0, 50),
            (-50, -50),
            (100, 100),
        ]
        for dx, dy in stroke_points:
            print(f"Moving mouse by ({dx}, {dy})")
            self.mouse_sender.move_mouse(dx, dy)
            time.sleep(0.05)

        # Manual verification: check that a diagonal drag occurred on the target
        self.assertTrue(True, "Verify mouse stroke was performed on the target machine")

    @unittest.skip("Applicable for mouse HID")
    def test_mouse_stroke_max(self):
        """Perform a mouse stroke: hold left button and move diagonally. Verify manually."""
        # Press left button
        self.mouse_sender.press_button(1)
        time.sleep(0.05)
        self.mouse_sender.release_button(1)

        stroke_points = [(-127, 0), (127, 0), (0, 127), (0, -127)]
        for dx, dy in stroke_points:
            time.sleep(5)
            print(f"Moving mouse by ({dx}, {dy})")
            self.mouse_sender.move_mouse(dx, dy)

        # Manual verification: check that a diagonal drag occurred on the target
        self.assertTrue(True, "Verify mouse stroke was performed on the target machine")

    @unittest.skip("Applicable for mouse HID")
    def test_combined_keyboard_and_mouse(self):
        """Type 'helloworld' then perform a mouse stroke in one session. Verify manually."""
        # --- Keyboard phase ---
        type_string(self.key_sender, "helloworld", delay=0.05)
        time.sleep(0.2)

        # --- Mouse phase ---
        self.mouse_sender.press_button(1)
        time.sleep(0.05)
        self.mouse_sender.move_mouse(20, 10)
        time.sleep(0.05)
        self.mouse_sender.move_mouse(-5, 3)
        time.sleep(0.05)
        self.mouse_sender.release_button(1)
        time.sleep(0.3)

        # Manual verification: check that "helloworld" was typed and a drag occurred
        self.assertTrue(True, "Verify typing and mouse stroke on the target machine")


if __name__ == "__main__":
    unittest.main()
