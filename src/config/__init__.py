# config パッケージ: sim / game / client の3層設定を読み込む
import json
from pathlib import Path
from typing import Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Config:
    """シミュレーション・ゲーム・クライアント各層の設定を分離して保持する。"""

    def __init__(self):
        self.base_path = _PROJECT_ROOT / "config"
        self.sim = self._load("sim/engine.json")
        self.game_app = self._load("game/app.json")
        self.game_player = self._load("game/player.json")
        self.client = self._load("client/display.json")
        self.worlds = self._load_all("sim/worlds")
        self.species = self._load_all("sim/species")
        self.object_types = self._load_object_types("sim/object_types")

    def _load(self, rel_path: str) -> Dict:
        path = self.base_path / rel_path
        if not path.exists():
            print(f"警告: {path} が見つかりません")
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _load_all(self, folder: str) -> Dict:
        data = {}
        folder_path = self.base_path / folder
        if not folder_path.exists():
            print(f"警告: {folder_path} フォルダが見つかりません")
            return data

        for json_file in sorted(folder_path.glob("*.json")):
            try:
                with open(json_file, encoding="utf-8") as f:
                    item = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"警告: {json_file.name} の読み込みに失敗: {e}")
                continue
            if "name" in item:
                data[item["name"]] = item
            else:
                print(f"警告: {json_file.name} に 'name' キーがありません")
        return data

    def _load_object_types(self, folder: str) -> Dict:
        data: Dict = {}
        folder_path = self.base_path / folder
        if not folder_path.exists():
            return data

        for json_file in sorted(folder_path.glob("*.json")):
            try:
                with open(json_file, encoding="utf-8") as f:
                    item = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"警告: {json_file.name} の読み込みに失敗: {e}")
                continue
            type_id = item.get("id")
            if not type_id:
                print(f"警告: {json_file.name} に 'id' キーがありません")
                continue
            data[str(type_id)] = item
        return data

    def reload_all(self) -> None:
        """全 JSON をディスクから再読み込み（R リセット時など）。"""
        self.sim = self._load("sim/engine.json")
        self.game_app = self._load("game/app.json")
        self.game_player = self._load("game/player.json")
        self.client = self._load("client/display.json")
        self.worlds = self._load_all("sim/worlds")
        self.species = self._load_all("sim/species")
        self.object_types = self._load_object_types("sim/object_types")

    def get_world(self, name: str = "Grassland") -> Optional[Dict]:
        if name in self.worlds:
            return self.worlds[name]
        lower = name.lower()
        for key, value in self.worlds.items():
            if key.lower() == lower:
                return value
        if "Grassland" in self.worlds:
            return self.worlds["Grassland"]
        return next(iter(self.worlds.values()), None)

    def get_species(self, name: str = "springtail") -> Dict:
        if name in self.species:
            return self.species[name]
        lower = name.lower()
        for key, value in self.species.items():
            if key.lower() == lower:
                return value
        return self.species.get("springtail", next(iter(self.species.values()), {}))

    def get_object_type(self, type_id: str) -> Dict:
        if type_id in self.object_types:
            return self.object_types[type_id]
        lower = type_id.lower()
        for key, value in self.object_types.items():
            if key.lower() == lower:
                return value
        return {}


config = Config()
