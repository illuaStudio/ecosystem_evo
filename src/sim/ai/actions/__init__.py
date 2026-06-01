from src.sim.ai.actions.base import Action
from src.sim.ai.actions.combat_actions import CombatAction
from src.sim.ai.actions.movement import FleeAction, WanderAction
from src.sim.ai.actions.predation import ChaseAction, HuntAction
from src.sim.ai.actions.registry import ACTION_BY_NAME, register_action_aliases
from src.sim.ai.actions.reproduction import ReproductionAction

SIM_ACTIONS = {
    "WanderAction": WanderAction,
    "ChaseAction": ChaseAction,
    "CombatAction": CombatAction,
    "FleeAction": FleeAction,
    "HuntAction": HuntAction,
    "ReproductionAction": ReproductionAction,
}

register_action_aliases(SIM_ACTIONS)

__all__ = [
    "Action",
    "ACTION_BY_NAME",
    "ChaseAction",
    "CombatAction",
    "FleeAction",
    "HuntAction",
    "ReproductionAction",
    "WanderAction",
]
