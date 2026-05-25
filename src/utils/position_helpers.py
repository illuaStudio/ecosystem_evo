"""座標の単一ソース（Position コンポーネント）とレガシー pos の同期。"""
from typing import Any, Tuple


def entity_xy(entity: Any) -> Tuple[float, float]:
    """
    エンティティのワールド座標を返す。
    Position コンポーネントがあればそれを正とし、なければ BaseEntity.pos にフォールバックする。
    """
    position = getattr(entity, "position", None)
    if position is not None:
        return position.x, position.y

    pos = getattr(entity, "pos", None)
    if pos is not None:
        return float(pos[0]), float(pos[1])

    raise AttributeError(f"{type(entity).__name__} に座標がありません")


def sync_legacy_pos(entity: Any, *, update_last: bool = False) -> None:
    """
    Position → pos（および任意で last_pos）へ同期する。
    移動・行動のあとに呼び、描画・距離計算など pos 参照側を整合させる。
    """
    position = getattr(entity, "position", None)
    if position is None:
        return

    if hasattr(entity, "pos"):
        entity.pos[0] = position.x
        entity.pos[1] = position.y

    if update_last and hasattr(entity, "last_pos"):
        entity.last_pos[0] = position.x
        entity.last_pos[1] = position.y
