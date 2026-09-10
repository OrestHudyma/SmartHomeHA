"""Open only the configured serial port; reuse the upstream wire protocol."""
import threading
import serial
from periphery import HWInterface


class HardwareAdapter(HWInterface):
    def __init__(self, port, serial_factory=serial.Serial):
        # Deliberately replace discovery, not test() or transmit_fm433().
        self._transmit_lock = threading.Lock()
        self.com_port = None
        connection = serial_factory(port, baudrate=self.BOUDRATE,
                                    timeout=self.TIMEOUT, write_timeout=self.TIMEOUT,
                                    exclusive=True)
        try:
            connection.reset_input_buffer()
            if not self.test(connection):
                raise ConnectionError("Selected port did not answer the controller handshake")
            self.com_port = connection
        except BaseException:
            connection.close()
            raise

    def close(self):
        connection, self.com_port = self.com_port, None
        if connection is not None:
            connection.close()
