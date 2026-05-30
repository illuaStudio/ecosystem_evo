from src.ai.actions.base import Action
from src.ai.actions.colony import (
    FeedAtNestAction,
    NestPatrolAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
)
from src.ai.actions.combat_actions import AttackHoleAction, CombatAction
from src.ai.actions.movement import (
    FleeAction,
    ManaGradientWanderAction,
    ManaWanderAction,
    WanderAction,
)
from src.ai.actions.predation import ChaseAction, HuntAction
from src.ai.actions.reproduction import (
    ColonyReproduceAction,
    ReproductionAction,
    SpawnWorkerAction,
    SplitAction,
)
from src.ai.actions.shelter import SeekShelterAction

ACTION_BY_NAME = {
    "WanderAction": WanderAction,
    "ManaWanderAction": ManaWanderAction,
    "ManaGradientWanderAction": ManaGradientWanderAction,
    "ChaseAction": ChaseAction,
    "CombatAction": CombatAction,
    "AttackHoleAction": AttackHoleAction,
    "FleeAction": FleeAction,
    "SeekShelterAction": SeekShelterAction,
    "HuntAction": HuntAction,
    "ReturnToNestAction": ReturnToNestAction,
    "ScavengeCarriedAction": ScavengeCarriedAction,
    "FeedAtNestAction": FeedAtNestAction,
    "NestPatrolAction": NestPatrolAction,
    "ColonyReproduceAction": ColonyReproduceAction,
    "SpawnWorkerAction": SpawnWorkerAction,
    "SplitAction": SplitAction,
}

__all__ = [
    "Action",
    "ACTION_BY_NAME",
    "AttackHoleAction",
    "ChaseAction",
    "CombatAction",
    "FeedAtNestAction",
    "FleeAction",
    "SeekShelterAction",
    "HuntAction",
    "ManaGradientWanderAction",
    "ManaWanderAction",
    "NestPatrolAction",
    "ReproductionAction",
    "ReturnToNestAction",
    "ScavengeCarriedAction",
    "ColonyReproduceAction",
    "SpawnWorkerAction",
    "SplitAction",
    "WanderAction",
]
