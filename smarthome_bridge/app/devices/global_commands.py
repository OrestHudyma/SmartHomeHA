import periphery
from .base import Adapter


class GlobalAdapter(Adapter):
    singleton = True
    buttons = {
        "day": ("Day", "day_light"),
        "night": ("Night", "night_light"),
    }

    @staticmethod
    def create(interface, ident):
        return periphery.DeviceGlobal(interface)
