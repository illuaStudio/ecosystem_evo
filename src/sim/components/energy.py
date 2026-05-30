from dataclasses import dataclass


@dataclass
class Energy:
    """将来のエネルギー管理用（Phase 1 ではプレースホルダ）。"""

    value: float = 0.0
    max_value: float = 100.0
