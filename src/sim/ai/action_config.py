"""Action JSON params: コード既定へのフォールバックなし（欠落は即エラー）。"""
from __future__ import annotations

from src.sim.ai.actions.base import Action


def missing_action_param_keys(action_cls: type[Action], params: dict) -> list[str]:
    defaults = getattr(action_cls, "DEFAULT_PARAMS", None) or {}
    return sorted(k for k in defaults if k not in params)


def require_action_params(
    action_cls: type[Action],
    params: dict | None,
    *,
    source: str = "",
) -> dict:
    data = dict(params or {})
    missing = missing_action_param_keys(action_cls, data)
    if missing:
        where = f" ({source})" if source else ""
        raise KeyError(
            f"{action_cls.__name__}{where}: params に必須キーがありません: {missing}"
        )
    return data


def expand_action_params(action_cls: type[Action], params: dict | None) -> dict:
    """JSON 編集用: 既存 params に DEFAULT_PARAMS の欠落キーを埋める（書き込み専用）。"""
    merged = dict(getattr(action_cls, "DEFAULT_PARAMS", None) or {})
    merged.update(params or {})
    return merged


def get_mind_action_param(creature, action_name: str, param_name: str) -> float:
    """種 mind.actions から Action の params 値を取得（欠落時 KeyError）。"""
    for act in creature.species.mind_data.get("actions", []):
        if act.get("name") != action_name:
            continue
        params = act.get("params") or {}
        if param_name not in params:
            raise KeyError(
                f"species {creature.species.name}: "
                f"mind.actions {action_name}.params.{param_name} required"
            )
        return float(params[param_name])
    raise KeyError(
        f"species {creature.species.name}: mind.actions {action_name} not found"
    )
