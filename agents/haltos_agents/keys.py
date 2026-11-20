"""Turns a Qt key press into the bytes an xterm sends, without importing Qt."""

# Qt's modifier bits and key codes, copied so this module stays Qt-free.
SHIFT = 0x02000000
CTRL = 0x04000000
ALT = 0x08000000


class Key:
    ESCAPE = 0x01000000
    TAB = 0x01000001
    BACKTAB = 0x01000002
    BACKSPACE = 0x01000003
    ENTER = 0x01000004
    KEYPAD_ENTER = 0x01000005
    INSERT = 0x01000006
    DELETE = 0x01000007
    HOME = 0x01000010
    END = 0x01000011
    LEFT = 0x01000012
    UP = 0x01000013
    RIGHT = 0x01000014
    DOWN = 0x01000015
    PAGE_UP = 0x01000016
    PAGE_DOWN = 0x01000017


CURSOR = {Key.UP: "A", Key.DOWN: "B", Key.RIGHT: "C", Key.LEFT: "D", Key.HOME: "H", Key.END: "F"}
TILDE = {Key.INSERT: 2, Key.DELETE: 3, Key.PAGE_UP: 5, Key.PAGE_DOWN: 6}


def encode(key: int, text: str, mods: int) -> bytes:
    shift, ctrl, alt = bool(mods & SHIFT), bool(mods & CTRL), bool(mods & ALT)
    # xterm's modifier parameter: 1 plus shift 1, alt 2, ctrl 4.
    param = 1 + shift + 2 * alt + 4 * ctrl
    if key in CURSOR:
        return f"\x1b[{CURSOR[key]}".encode() if param == 1 else f"\x1b[1;{param}{CURSOR[key]}".encode()
    if key in TILDE:
        return f"\x1b[{TILDE[key]}~".encode() if param == 1 else f"\x1b[{TILDE[key]};{param}~".encode()
    prefix = b"\x1b" if alt else b""
    if key in (Key.ENTER, Key.KEYPAD_ENTER):
        # Claude Code takes Esc+Enter as a new line, the way Option+Enter arrives from macOS terminals.
        return b"\x1b\r" if shift else prefix + b"\r"
    if key == Key.BACKTAB or (key == Key.TAB and shift):
        return b"\x1b[Z"
    if key == Key.TAB:
        return prefix + b"\t"
    if key == Key.ESCAPE:
        return b"\x1b"
    if key == Key.BACKSPACE:
        return prefix + (b"\x08" if ctrl else b"\x7f")
    if ctrl and 0x40 <= key <= 0x5F:
        return prefix + bytes([key - 0x40])
    if ctrl and key == 0x20:
        return prefix + b"\x00"
    if text and text.isprintable():
        return prefix + text.encode("utf8")
    return b""
