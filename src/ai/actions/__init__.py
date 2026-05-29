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
from src.ai.actions.reproduction import ReproductionAction, SpawnWorkerAction, SplitAction

ACTION_BY_NAME = {
    "WanderAction": WanderAction,
    "ManaWanderAction": ManaWanderAction,
    "ManaGradientWanderAction": ManaGradientWanderAction,
    "ChaseAction": ChaseAction,
    "CombatAction": CombatAction,
    "AttackHoleAction": AttackHoleAction,
    "FleeAction": FleeAction,
    "HuntAction": HuntAction,
    "ReturnToNestAction": ReturnToNestAction,
    "ScavengeCarriedAction": ScavengeCarriedAction,
    "FeedAtNestAction": FeedAtNestAction,
    "NestPatrolAction": NestPatrolAction,
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
    "HuntAction",
    "ManaGradientWanderAction",
    "ManaWanderAction",
    "NestPatrolAction",
    "ReproductionAction",
    "ReturnToNestAction",
    "ScavengeCarriedAction",
    "SpawnWorkerAction",
    "SplitAction",
    "WanderAction",
]
