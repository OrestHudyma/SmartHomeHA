import periphery
from .base import Adapter


class GlobalAdapter(Adapter):
    singleton = True
    buttons = {
        "day": ("День", "day_light"),
        "night": ("Ніч", "night_light"),
    }

    @staticmethod
    def create(interface, ident):
        return periphery.DeviceGlobal(interface)
