# USB loopback

Sends mouse actions and keystrokes from client to server using TCP sockets.

The server writes HID report to USB device file descriptors.

Adjust SCREEN_WIDTH and SCREEN_HEIGHT (usb_loopback\client\io_interface.py) for correct mouse coordinate scaling.

# Message formats

The payloads follow HID mouse/keyboard aside from the initial msg_type byte.

## Message struct
| Byte Size | Description |
| -- | -- |
| 1 | msg_type |
| variable | payload |

## msg_type
| Name | Description |
| -- | -- |
| msg_type | 0 for keyboard, 1 for mouse |

## Mouse payload struct

| Byte Size | Description |
| -- | -- |
| 1 | 0x1 = left mouse button, 0x2 = right mouse button, 0x4 = middle mouse button |
| 2 | x mouse coordinate (absolute), scaled from screen width to 0x7FFF |
| 2 | y mouse coordinate (absolute), scaled from screen height to 0x7FFF |
| 1 | scroll wheel (0) |

## Keystroke payload struct

| Byte Size | Description |
| -- | -- |
| 1 | Modifier mask |
| 1 | Reserved (0) |
| 6 | Key codes, 1 per byte |
