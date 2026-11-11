import unittest
import os
import tempfile
import threading
import time

from usb_loopback.client.io_interface import SocketKeySender, SocketMouseSender
from usb_loopback.server.server import HIDServer


class TestUSBLoopbackIOInterface(unittest.TestCase):
    """Test cases for USB Loopback client-server IO interface."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary files to act as HID devices
        self.keyboard_temp = tempfile.NamedTemporaryFile(delete=False)
        self.mouse_temp = tempfile.NamedTemporaryFile(delete=False)
        self.keyboard_temp.close()
        self.mouse_temp.close()

        # Store paths for cleanup
        self.keyboard_device = self.keyboard_temp.name
        self.mouse_device = self.mouse_temp.name

        # Start server in a separate thread on a dynamic port
        self.server = HIDServer(
            host="127.0.0.1",
            port=0,
            keyboard_device=self.keyboard_device,
            mouse_device=self.mouse_device,
        )
        self.server_thread = threading.Thread(target=self.server.start)
        self.server_thread.daemon = True
        self.server_thread.start()

        # Wait for server to be ready
        if not self.server.ready_event.wait(timeout=2.0):
            if not self.server_thread.is_alive():
                self.fail("Server thread died during initialization. Check logs.")
            self.fail("Server failed to start listening within timeout")

        # Get the actual port assigned by the OS
        self.server_port = self.server.server_socket.getsockname()[1]

        # Create client senders
        self.key_sender = SocketKeySender(host="127.0.0.1", port=self.server_port)
        self.mouse_sender = SocketMouseSender(host="127.0.0.1", port=self.server_port)

    def tearDown(self):
        """Tear down test fixtures."""
        # Stop server
        self.server.stop()
        if self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0)

        # Clean up temporary files
        try:
            os.unlink(self.keyboard_device)
            os.unlink(self.mouse_device)
        except OSError:
            pass

    def test_keyboard_key_press(self):
        """Test sending a single key press."""
        # Send key 'a' (HID keycode 0x04)
        self.key_sender.send_key(0x04)

        # Give time for transmission
        time.sleep(0.2)

        # Read the keyboard device file
        with open(self.keyboard_device, "rb") as f:
            data = f.read()

        # Should have at least one 8-byte report
        self.assertGreaterEqual(len(data), 8)

        # Check the first report
        report = data[:8]
        expected = bytes([0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.assertEqual(
            report,
            expected,
            f"Expected keyboard report {expected.hex()}, got {report.hex()}",
        )

    @unittest.skip("Applicable for mouse HID")
    def test_mouse_movement_and_click(self):
        """Test mouse movement and button click."""
        # Press left button
        self.mouse_sender.press_button(1)
        # Move mouse right 10, down 5
        self.mouse_sender.move_mouse(10, 5)
        # Release left button
        self.mouse_sender.release_button(1)

        # Give time for transmission
        time.sleep(0.2)

        # Read the mouse device file
        with open(self.mouse_device, "rb") as f:
            data = f.read()

        # Should have at least three 3-byte reports (press, move, release)
        self.assertGreaterEqual(len(data), 9)  # At least 3 reports

        # Check first report (button press)
        report1 = data[0:3]
        expected1 = bytes([0x01, 0x00, 0x00])  # Left button pressed, no movement
        self.assertEqual(
            report1,
            expected1,
            f"Expected mouse press report {expected1.hex()}, got {report1.hex()}",
        )

        # Check second report (movement)
        report2 = data[3:6]
        expected2 = bytes([0x01, 0x0A, 0x05])  # Left button still pressed, x=10, y=5
        self.assertEqual(
            report2,
            expected2,
            f"Expected mouse move report {expected2.hex()}, got {report2.hex()}",
        )

        # Check third report (button release)
        report3 = data[6:9]
        expected3 = bytes([0x00, 0x00, 0x00])  # No buttons, no movement
        self.assertEqual(
            report3,
            expected3,
            f"Expected mouse release report {expected3.hex()}, got {report3.hex()}",
        )

    def test_key_combination(self):
        """Test sending a key combination (simplified)."""
        # Send key combination: left shift (0xE1) + 'a' (0x04)
        # In our simplified implementation, we'll just send the keycode
        self.key_sender.send_key_combination([0xE1, 0x04])

        # Give time for transmission
        time.sleep(0.2)

        # Read the keyboard device file
        with open(self.keyboard_device, "rb") as f:
            data = f.read()

        # Should have at least one 8-byte report
        self.assertGreaterEqual(len(data), 8)

        # Check the first report (we expect the first keycode in the list)
        # Check the first report (we expect modifier and packed keycode)
        report = data[:8]
        # Our implementation puts the first keycode in the report
        expected = bytes([0x00, 0x00, 0xE1, 0x00, 0x00, 0x00, 0x00, 0x00])
        # Expected: Modifier 0x02 (LShift) + Reserved + Keycode 0x04 ('a')
        expected = bytes([0x02, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.assertEqual(
            report,
            expected,
            f"Expected key combination report {expected.hex()}, got {report.hex()}",
        )


if __name__ == "__main__":
    unittest.main()
