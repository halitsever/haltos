import unittest

from haltos_agents.keys import ALT, CTRL, SHIFT, Key, encode


class EncodeTest(unittest.TestCase):
    def test_text_passes_through(self):
        self.assertEqual(encode(0x41, "a", 0), b"a")
        self.assertEqual(encode(0x41, "ş", 0), "ş".encode())

    def test_special_keys(self):
        self.assertEqual(encode(Key.ENTER, "\r", 0), b"\r")
        self.assertEqual(encode(Key.ESCAPE, "\x1b", 0), b"\x1b")
        self.assertEqual(encode(Key.BACKSPACE, "\x08", 0), b"\x7f")
        self.assertEqual(encode(Key.TAB, "\t", 0), b"\t")
        self.assertEqual(encode(Key.BACKTAB, "", SHIFT), b"\x1b[Z")
        self.assertEqual(encode(Key.UP, "", 0), b"\x1b[A")
        self.assertEqual(encode(Key.LEFT, "", 0), b"\x1b[D")
        self.assertEqual(encode(Key.DELETE, "", 0), b"\x1b[3~")
        self.assertEqual(encode(Key.PAGE_UP, "", 0), b"\x1b[5~")

    def test_shift_enter_is_a_new_line(self):
        self.assertEqual(encode(Key.ENTER, "\r", SHIFT), b"\x1b\r")

    def test_ctrl_letters(self):
        self.assertEqual(encode(ord("C"), "\x03", CTRL), b"\x03")
        self.assertEqual(encode(ord("R"), "", CTRL), b"\x12")

    def test_alt_prefixes_escape(self):
        self.assertEqual(encode(ord("B"), "b", ALT), b"\x1bb")
        self.assertEqual(encode(Key.LEFT, "", ALT), b"\x1b[1;3D")

    def test_unknown_key_sends_nothing(self):
        self.assertEqual(encode(0x01000020, "", SHIFT), b"")


if __name__ == "__main__":
    unittest.main()
