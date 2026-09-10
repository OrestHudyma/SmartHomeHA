class Adapter:
    singleton = False
    power_domain = None
    buttons = {}

    @staticmethod
    def validate_id(ident):
        pass

    def __init__(self, config, interface):
        self.config = config
        self.device = self.create(interface, config.id)

    @property
    def actions(self):
        result = {key: ("PRESS",) for key in self.buttons}
        if self.power_domain:
            result["power"] = ("ON", "OFF")
        return result

    def execute(self, action, payload):
        if payload not in self.actions.get(action, ()):
            raise ValueError("Unsupported command")
        if action == "power":
            return getattr(self.device, "power_on" if payload == "ON" else "power_off")()
        return getattr(self.device, self.buttons[action][1])()
