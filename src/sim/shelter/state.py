"""避難状態（他モジュールからの循環 import を避けるため分離）。"""


def shelter_allowed_action_names(world) -> frozenset[str]:
    """ゲーム層が attach_colony_orchestrator で設定する許可行動名。"""
    return getattr(world, "shelter_allowed_action_names", frozenset())


def is_creature_sheltered(creature) -> bool:
    return getattr(creature, "shelter", None) is not None


def clear_creature_shelter(creature) -> None:
    creature.shelter = None
