from src.sim.ai.actions.base import Action
from src.sim.ai.actions.colony import (
    FeedAtNestAction,
    NestPatrolAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
)
from src.sim.ai.actions.combat_actions import AttackHoleAction, CombatAction
from src.sim.ai.actions.movement import FleeAction, WanderAction
from src.sim.ai.actions.predation import ChaseAction, HuntAction
from src.sim.ai.actions.reproduction import (
    ColonyReproduceAction,
    ReproductionAction,
    SpawnWorkerAction,
)
from src.sim.ai.actions.shelter import SeekShelterAction

ACTION_BY_NAME = {
    "WanderAction": WanderAction,
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
    "NestPatrolAction",
    "ReproductionAction",
    "ReturnToNestAction",
    "ScavengeCarriedAction",
    "ColonyReproduceAction",
    "SpawnWorkerAction",
    "WanderAction",
]
