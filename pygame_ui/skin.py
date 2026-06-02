"""画像スキン（PNG）と 9-slice 定義。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

_PACKAGE_DIR = Path(__file__).resolve().parent
BUILTIN_SKINS_DIR = _PACKAGE_DIR / "assets" / "skins"


def _load_image_alpha(path: Path) -> object:
    """PNG を読み込み。ディスプレイ未初期化時は convert_alpha をスキップ。"""
    import pygame

    surf = pygame.image.load(str(path))
    try:
        return surf.convert_alpha()
    except pygame.error:
        return surf


@dataclass(frozen=True)
class NineSliceSpec:
    """角・辺・中央を伸縮して矩形に描画するスキン。"""

    surface: object  # pygame.Surface
    left: int
    top: int
    right: int
    bottom: int

    @property
    def min_width(self) -> int:
        return self.left + self.right + 1

    @property
    def min_height(self) -> int:
        return self.top + self.bottom + 1


@dataclass
class UISkin:
    """ウィジェット別のビットマップスキン。未設定の部位はベクター描画にフォールバック。"""

    name: str = "unnamed"
    images: Dict[str, object] = field(default_factory=dict)  # key -> Surface
    nine_slice: Dict[str, NineSliceSpec] = field(default_factory=dict)

    def image(self, key: str) -> Optional[object]:
        return self.images.get(key)

    def slice_spec(self, key: str) -> Optional[NineSliceSpec]:
        return self.nine_slice.get(key)

    def has(self, key: str) -> bool:
        return key in self.images or key in self.nine_slice

    @classmethod
    def from_directory(cls, directory: str | Path) -> "UISkin":
        """`skin.json` + PNG を読み込む。"""
        import pygame

        root = Path(directory)
        manifest_path = root / "skin.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"skin.json not found: {manifest_path}")

        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)

        name = str(data.get("name", root.name))
        images: Dict[str, object] = {}
        for key, filename in (data.get("images") or {}).items():
            path = root / str(filename)
            if path.is_file():
                images[str(key)] = _load_image_alpha(path)

        nine_slice: Dict[str, NineSliceSpec] = {}
        for key, spec in (data.get("nine_slice") or {}).items():
            filename = spec.get("image") or spec.get("file")
            if not filename:
                continue
            path = root / str(filename)
            if not path.is_file():
                continue
            surf = _load_image_alpha(path)
            nine_slice[str(key)] = NineSliceSpec(
                surface=surf,
                left=int(spec.get("left", 4)),
                top=int(spec.get("top", 4)),
                right=int(spec.get("right", 4)),
                bottom=int(spec.get("bottom", 4)),
            )

        return cls(name=name, images=images, nine_slice=nine_slice)

    @classmethod
    def load_builtin(cls, skin_id: str) -> "UISkin":
        """`pygame_ui/assets/skins/<id>/` を読み込む。"""
        return cls.from_directory(BUILTIN_SKINS_DIR / skin_id)
