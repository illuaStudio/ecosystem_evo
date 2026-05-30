"""テスト用ワールド JSON 断片（コード既定フォールバックなし）。"""

RED_ANT_PROFILE = {
    "nest_x": 120,
    "nest_y": 120,
    "territory_radius": 180,
    "max_food": 5000,
    "initial_stored_food": 80,
    "food_leak_rate": 0.00012,
    "food_to_mana_ratio": 0.35,
    "food_leak_reserve_ratio": 0.15,
    "spawn_spread": 28,
}

BLUE_ANT_PROFILE = {
    "nest_x": 500,
    "nest_y": 820,
    "territory_radius": 180,
    "max_food": 5000,
    "initial_stored_food": 80,
    "food_leak_rate": 0.00012,
    "food_to_mana_ratio": 0.35,
    "food_leak_reserve_ratio": 0.15,
    "spawn_spread": 28,
}

YELLOW_ANT_PROFILE = {
    "nest_x": 880,
    "nest_y": 120,
    "territory_radius": 180,
    "max_food": 5000,
    "initial_stored_food": 80,
    "food_leak_rate": 0.00012,
    "food_to_mana_ratio": 0.35,
    "food_leak_reserve_ratio": 0.15,
    "spawn_spread": 28,
}


def colony_settings(**extra) -> dict:
    """巣穴・産卵共通 + 全コロニー profiles。"""
    base = {
        "min_food_reserve": 72,
        "profiles": {
            "red_ant": dict(RED_ANT_PROFILE),
            "blue_ant": dict(BLUE_ANT_PROFILE),
            "yellow_ant": dict(YELLOW_ANT_PROFILE),
        },
    }
    base.update(extra)
    return base
