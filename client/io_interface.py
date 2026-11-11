"""USB Loopback client IO interface that sends keystrokes and mouse movements over TCP socket."""

from abc import ABC, abstractmethod
import time
from typing import List

# Import the socket sender
from .socket_sender import SocketSender

# Screen resolution for absolute mouse positioning
SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1440

# HID absolute coordinate range (0-32767 per HID spec)
HID_MAX = 32767


def _screen_to_hid(x: int, y: int):
    """Convert screen pixel coordinates to HID absolute coordinates (0-32767).

    Args:
        x: Screen X coordinate in pixels (0 = left edge).
        y: Screen Y coordinate in pixels (0 = top edge).

    Returns:
        Tuple of (hid_x, hid_y) clamped to 0-32767.
    """
    hid_x = int((x / SCREEN_WIDTH) * HID_MAX)
    hid_y = int((y / SCREEN_HEIGHT) * HID_MAX)
    return max(0, min(HID_MAX, hid_x)), max(0, min(HID_MAX, hid_y))


class KeySender(ABC):
    """Abstract base class for sending keystrokes."""

    @abstractmethod
    def send_key(self, key_code: int) -> None:
        """Send a single key press.

        Args:
            key_code: The USB HID keycode to send.
        """
        pass

    @abstractmethod
    def send_key_combination(self, key_codes: List[int]) -> None:
        """Send a combination of keys pressed simultaneously.

        Args:
            key_codes: List of USB HID keycodes to send together.
        """
        pass

    @abstractmethod
    def release_all_keys(self) -> None:
        """Release all currently pressed keys."""
        pass


class MouseSender(ABC):
    """Abstract base class for sending mouse movements and button clicks."""

    @abstractmethod
    def move_mouse(self, x: int, y: int) -> None:
        """Move the mouse relative to its current position.

        Args:
            x: Relative movement on the X axis (positive right, negative left).
            y: Relative movement on the Y axis (positive down, negative up).
        """
        pass

    @abstractmethod
    def press_button(self, button: int) -> None:
        """Press a mouse button.

        Args:
            button: Button identifier (typically 1=left, 2=right, 3=middle, etc.).
        """
        pass

    @abstractmethod
    def release_button(self, button: int) -> None:
        """Release a mouse button.

        Args:
            button: Button identifier (typically 1=left, 2=right, 3=middle, etc.).
        """
        pass

    @abstractmethod
    def click_button(self, button: int) -> None:
        """Click a mouse button (press and release).

        Args:
            button: Button identifier (typically 1=left, 2=right, 3=middle, etc.).
        """
        pass

    @abstractmethod
    def move_mouse_absolute(self, x: int, y: int) -> None:
        """Move the mouse to an absolute screen position.

        Coordinates are screen pixel positions.  They are automatically
        scaled to the HID native range (0-32767) using the configured
        SCREEN_WIDTH and SCREEN_HEIGHT.

        Args:
            x: Screen X coordinate in pixels (0 = left edge).
            y: Screen Y coordinate in pixels (0 = top edge).
        """
        pass


class SocketKeySender(KeySender):
    """KeySender implementation that sends keystrokes over TCP socket to server."""

    def __init__(self, host="localhost", port=9999):
        self.sender = SocketSender(host, port)
        # Track currently pressed keys for combination handling
        self.pressed_keys = set()

    def send_key(self, key_code: int) -> None:
        """Send a single key press."""
        # Create HID keyboard report: modifier(1), reserved(1), keycodes(6)
        # For simplicity, we'll put the keycode in the first position and no modifiers
        report = [0x00, 0x00, key_code & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00]
        self.sender.send(0, bytes(report))  # 0 = keyboard type

    def send_key_combination(
        self, key_codes: List[int], auto_release: bool = True
    ) -> None:
        """
        Send a combination of keys pressed simultaneously.

        Args:
            key_codes: List of HID usage IDs (e.g., 0x04 for 'A', 0xE0 for Left Control).
            auto_release: If True, automatically sends a key-release report immediately after.
        """
        modifier = 0x00
        keycode_list = [0x00] * 6

        keycode_index = 0

        # Iterate over ALL items in key_codes, not just the first 6.
        for code in key_codes:
            # Cleaner check for modifier keys using range (0xE0 to 0xE7)
            if 0xE0 <= code <= 0xE7:
                # Set the appropriate modifier bit
                modifier |= 1 << (code - 0xE0)
            else:
                # Add standard keycodes up to the 6-key USB HID limit
                if keycode_index < 6:
                    keycode_list[keycode_index] = code & 0xFF
                    keycode_index += 1
                else:
                    # Optional: Handle N-Key Rollover limits (ignore extra keys or log a warning)
                    pass

        # Create standard 8-byte HID keyboard report:
        # Byte 0: Modifier mask
        # Byte 1: Reserved (0x00)
        # Bytes 2-7: Up to 6 keycodes
        report = [modifier, 0x00] + keycode_list
        self.sender.send(0, bytes(report))  # 0 = keyboard type

    def release_all_keys(self) -> None:
        """Release all currently pressed keys."""
        # Send empty key report
        report = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        self.sender.send(0, bytes(report))  # 0 = keyboard type


class SocketMouseSender(MouseSender):
    """MouseSender implementation that sends mouse movements over TCP socket to server."""

    def __init__(self, host="localhost", port=9999):
        self.sender = SocketSender(host, port)
        # Track button states
        self.pressed_buttons = set()

    def move_mouse(self, x: int, y: int) -> None:
        """Move the mouse relative to its current position."""
        # Create HID mouse report: buttons(1), x(1), y(1)
        # Calculate button bits from pressed buttons
        buttons = 0x00
        if 1 in self.pressed_buttons:  # Left button
            buttons |= 0x01
        if 2 in self.pressed_buttons:  # Right button
            buttons |= 0x02
        if 3 in self.pressed_buttons:  # Middle button
            buttons |= 0x04

        # Clamp x and y to signed 8-bit range (-127 to 127)
        x = max(-127, min(127, x))
        y = max(-127, min(127, y))

        report = [buttons, x & 0xFF, y & 0xFF, 0]
        self.sender.send(1, bytes(report))  # 1 = mouse type

    def press_button(self, button: int) -> None:
        """Press a mouse button."""
        self.pressed_buttons.add(button)
        # Send button state change
        self._send_button_report()

    def release_button(self, button: int) -> None:
        """Release a mouse button."""
        self.pressed_buttons.discard(button)
        # Send button state change
        self._send_button_report()

    def click_button(self, button: int) -> None:
        """Click a mouse button (press and release)."""
        self.press_button(button)
        time.sleep(0.1)
        self.release_button(button)

    def move_mouse_absolute(self, x: int, y: int) -> None:
        """Move the mouse to an absolute screen position.

        Sends a 6-byte absolute mouse report (msg_type=2):
        buttons(1) + x_low(1) + x_high(1) + y_low(1) + y_high(1) + wheel(1)

        X and Y are screen pixel coordinates that are automatically
        converted to the HID native range (0-32767) using the formula:
            hid_value = screen_coord / screen_resolution * 32767
        """
        buttons = 0x00
        if 1 in self.pressed_buttons:  # Left button
            buttons |= 0x01
        if 2 in self.pressed_buttons:  # Right button
            buttons |= 0x02
        if 3 in self.pressed_buttons:  # Middle button
            buttons |= 0x04

        # Convert screen pixel coordinates to HID absolute range (0-32767)
        hid_x, hid_y = _screen_to_hid(x, y)

        report = [
            buttons,
            hid_x & 0xFF,
            (hid_x >> 8) & 0xFF,
            hid_y & 0xFF,
            (hid_y >> 8) & 0xFF,
            0x00,  # scroll wheel (no scroll)
        ]
        self.sender.send(2, bytes(report))  # 2 = absolute mouse type

    def _send_button_report(self) -> None:
        """Send current button state using 6-byte absolute mouse report."""
        buttons = 0x00
        if 1 in self.pressed_buttons:  # Left button
            buttons |= 0x01
        if 2 in self.pressed_buttons:  # Right button
            buttons |= 0x02
        if 3 in self.pressed_buttons:  # Middle button
            buttons |= 0x04

        # 6-byte absolute mouse report: buttons(1) + x(2) + y(2) + wheel(1)
        # Position is (0, 0) since this is a button-only report
        report = [buttons, 0x00, 0x00, 0x00, 0x00, 0x00]
        self.sender.send(2, bytes(report))  # 2 = absolute mouse type


# Factory functions to create the appropriate sender based on availability
def create_key_sender(host="localhost", port=9999) -> KeySender:
    """Create a KeySender instance."""
    return SocketKeySender(host, port)


def create_mouse_sender(host="localhost", port=9999) -> MouseSender:
    """Create a MouseSender instance."""
    return SocketMouseSender(host, port)
