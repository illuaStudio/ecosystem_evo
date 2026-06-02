"""避難状態（他モジュールからの循環 import を避けるため分離）。"""


def is_creature_sheltered(creature) -> bool:
    return getattr(creature, "shelter", None) is not None


def clear_creature_shelter(creature) -> None:
    creature.shelter = None
