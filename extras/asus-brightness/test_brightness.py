import unittest
from brightness import raw_brightness


class BrightnessTests(unittest.TestCase):
    def test_day_is_hardware_maximum(self):
        self.assertEqual(raw_brightness(b'100', 796875), 796875)

    def test_night_is_fifteen_percent(self):
        self.assertEqual(raw_brightness(b'15', 796875), 119531)

    def test_never_blanks_low_resolution_backlight(self):
        self.assertEqual(raw_brightness(b'1', 15), 1)

    def test_invalid_commands(self):
        for value in (b'0', b'101', b'-1', b'night', b'15.5', b'', b'\xff'):
            with self.subTest(value=value):
                with self.assertRaises((ValueError, UnicodeError)):
                    raw_brightness(value, 796875)


if __name__ == '__main__':
    unittest.main()
