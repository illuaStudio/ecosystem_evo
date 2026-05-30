"""Client 層: 描画・入力・pygame アプリ。"""

__all__ = ["GameApp"]


def __getattr__(name: str):
    if name == "GameApp":
        from src.client.app import GameApp

        return GameApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
