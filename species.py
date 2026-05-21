from config import config

class Species:
    @classmethod
    def create(cls, name: str = "Amoeba"):
        data = config.get_species(name)
        return cls(data)

    def __init__(self, data: dict):
        self.name = data["name"]
        self.color = tuple(data.get("color", [120, 200, 120]))
        self.traits = data["traits"]
        self.mind_data = data.get("mind", {"type": "priority", "actions": []})
        self.description = data.get("description", "")