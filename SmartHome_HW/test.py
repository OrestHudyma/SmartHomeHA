"""Host regression tests for the actual firmware; no PSoC tools or hardware needed."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
CASES = (
    'valid_checksum', 'invalid_checksum', 'missing_checksum', 'checksum_at_boundary',
    'complete_header', 'exact_command', 'invalid_characters', 'field_extraction',
    'field_boundaries', 'rx_overflow', 'resynchronize', 'pending_output',
    'transmit_interleaving', 'handshake_main',
)


class FirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which(os.environ.get('CC', 'gcc'))
        if compiler is None:
            raise RuntimeError('Install GCC or set CC to its executable path')
        directory = tempfile.TemporaryDirectory(prefix='smarthome-hw-tests-')
        cls.addClassCleanup(directory.cleanup)
        cls.binary = Path(directory.name) / ('firmware-test.exe' if os.name == 'nt' else 'firmware-test')
        flags = ['-std=c99', '-O1', '-g', '-Wall', '-Wextra', '-Werror']
        if os.environ.get('HW_TEST_SANITIZERS') == '1':
            flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
        subprocess.run([compiler, *flags, '-I', str(ROOT / 'tests'),
                        str(ROOT / 'tests/firmware_test.c'), '-o', str(cls.binary)],
                       check=True, timeout=60)


def case_test(name):
    def test(self):
        result = subprocess.run([str(self.binary), name], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    return test


for case in CASES:
    setattr(FirmwareTests, 'test_' + case, case_test(case))

if __name__ == '__main__':
    unittest.main()
