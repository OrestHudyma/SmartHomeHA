import periphery
import nmea
from .base import Adapter


class AlarmFitoLamp(periphery.FitoLamp):
    def alarm(self):
        return self.interface.transmit_fm433(
            nmea.compose("SHFTL", "ALARM", [self.device_id]))


class FitoLampAdapter(Adapter):
    power_domain = "light"
    buttons = {
        "fast_on": ("Fast on", "power_on_fast"),
        "fast_off": ("Fast off", "power_off_fast"),
        "alarm": ("Alarm", "alarm"),
    }

    @staticmethod
    def create(interface, ident):
        return AlarmFitoLamp(interface, ident)
