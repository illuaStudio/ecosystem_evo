from src.sim.ai.actions.base import Action
from src.sim.ai.actions.idle_locomotion import IdleLocomotionAction
from src.sim.ai.actions.registry import ACTION_BY_NAME, register_action_aliases

SIM_ACTIONS = {
    "IdleLocomotionAction": IdleLocomotionAction,
}

register_action_aliases(SIM_ACTIONS)

__all__ = [
    "Action",
    "ACTION_BY_NAME",
    "IdleLocomotionAction",
    "register_action_aliases",
]
