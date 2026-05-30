"""避難状態（他モジュールからの循環 import を避けるため分離）。"""

# 巣穴に隠れている間に Utility AI が選んでよい行動名
SHELTER_ALLOWED_ACTION_NAMES = frozenset({"SeekShelterAction", "FeedAtNestAction"})


def is_creature_sheltered(creature) -> bool:
    return getattr(creature, "shelter", None) is not None


def clear_creature_shelter(creature) -> None:
    creature.shelter = None
