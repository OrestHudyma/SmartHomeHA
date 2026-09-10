from .boiler import BoilerAdapter
from .fito_lamp import FitoLampAdapter
from .global_commands import GlobalAdapter


REGISTRY = {"boiler": BoilerAdapter, "fito_lamp": FitoLampAdapter, "global": GlobalAdapter}
