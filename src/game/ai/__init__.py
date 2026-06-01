"""ゲーム層 AI 行動の登録。"""
from src.game.ai.colony_actions import (
    AffiliationPatrolAction,
    FeedAtAffiliationSiteAction,
    FeedAtNestAction,
    NestPatrolAction,
    ReturnToAffiliationDepositAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
)
from src.game.ai.combat_actions import AttackHoleAction
from src.game.ai.reproduction_actions import (
    AffiliationReproduceAction,
    SpawnWorkerAction,
)
from src.game.ai.shelter_actions import SeekShelterAction
from src.sim.ai.actions.registry import register_action_aliases

GAME_ACTIONS = {
    "ScavengeCarriedAction": ScavengeCarriedAction,
    "ReturnToAffiliationDepositAction": ReturnToAffiliationDepositAction,
    "ReturnToNestAction": ReturnToNestAction,
    "FeedAtAffiliationSiteAction": FeedAtAffiliationSiteAction,
    "FeedAtNestAction": FeedAtNestAction,
    "AffiliationPatrolAction": AffiliationPatrolAction,
    "NestPatrolAction": NestPatrolAction,
    "AffiliationReproduceAction": AffiliationReproduceAction,
    "SpawnWorkerAction": SpawnWorkerAction,
    "SeekShelterAction": SeekShelterAction,
    "AttackHoleAction": AttackHoleAction,
}


def register_game_actions() -> None:
    from src.sim.ai.actions.registry import ACTION_BY_NAME

    missing = {k: v for k, v in GAME_ACTIONS.items() if k not in ACTION_BY_NAME}
    if missing:
        register_action_aliases(missing)
