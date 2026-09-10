import periphery
from .base import Adapter


class FitoLampAdapter(Adapter):
    power_domain = "light"
    buttons = {
        "fast_on": ("Fast on", "power_on_fast"),
        "fast_off": ("Fast off", "power_off_fast"),
    }

    @staticmethod
    def create(interface, ident):
        return periphery.FitoLamp(interface, ident)
