"""ゲーム層 AI 行動の登録。"""

from src.game.ai.chase_actions import ChaseAction
from src.game.ai.wander_actions import WanderAction
from src.game.ai.colony_actions import (
    AffiliationPatrolAction,
    FeedAtAffiliationSiteAction,
    FeedAtNestAction,
    NestPatrolAction,
    ReturnToAffiliationDepositAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
)
from src.game.ai.combat_actions import AttackHoleAction, CombatAction
from src.game.ai.flee_actions import FleeAction
from src.game.ai.hunt_actions import HuntAction
from src.game.ai.reproduction_actions import (
    AffiliationReproduceAction,
    ReproductionAction,
    SpawnWorkerAction,
)
from src.game.ai.shelter_actions import SeekShelterAction
from src.sim.ai.actions.registry import register_action_aliases

GAME_ACTIONS = {
    "WanderAction": WanderAction,
    "ChaseAction": ChaseAction,
    "CombatAction": CombatAction,
    "FleeAction": FleeAction,
    "ReproductionAction": ReproductionAction,
    "HuntAction": HuntAction,
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
