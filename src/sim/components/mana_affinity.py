from dataclasses import dataclass


@dataclass
class ManaAffinity:
    affinity: float = 1.0
    consumption_rate: float = 0.1
