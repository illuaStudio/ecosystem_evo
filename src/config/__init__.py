# config パッケージ: game.json / worlds / species を読み込む
import json
from pathlib import Path
from typing import Dict, Optional

# JSON データはプロジェクトルートの config/ に置く
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Config:
    def __init__(self):
        self.base_path = _PROJECT_ROOT / "config"

        self.game = self._load("game.json")
        self.worlds = self._load_all("worlds")
        self.species = self._load_all("species")

    def _load(self, filename: str) -> Dict:
        path = self.base_path / filename
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

    def reload_all(self) -> None:
        """game.json と worlds/species の全 JSON をディスクから再読み込み（R リセット時など）。"""
        self.game = self._load("game.json")
        self.worlds = self._load_all("worlds")
        self.species = self._load_all("species")

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

    def get_species(self, name: str = "Amoeba") -> Dict:
        if name in self.species:
            return self.species[name]
        lower = name.lower()
        for key, value in self.species.items():
            if key.lower() == lower:
                return value
        return self.species.get("Amoeba", next(iter(self.species.values()), {}))


config = Config()
