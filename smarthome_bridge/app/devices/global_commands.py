import periphery
import nmea
from .base import Adapter


class GlobalCommands(periphery.DeviceGlobal):
    def alarm(self):
        return self.interface.transmit_fm433(nmea.compose("SHGLB", "ALARM"))


class GlobalAdapter(Adapter):
    singleton = True
    buttons = {
        "day": ("Day", "day_light"),
        "night": ("Night", "night_light"),
        "alarm": ("Alarm", "alarm"),
    }

    @staticmethod
    def create(interface, ident):
        return GlobalCommands(interface)
