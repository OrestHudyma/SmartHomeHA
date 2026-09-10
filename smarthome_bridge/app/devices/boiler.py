import periphery
from .base import Adapter


class BoilerAdapter(Adapter):
    singleton = True  # The current radio protocol contains no boiler address.
    power_domain = "switch"

    @staticmethod
    def create(interface, ident):
        return periphery.Boiler(interface)

    @property
    def actions(self):
        return dict(super().actions, enabled=("ON", "OFF"))
