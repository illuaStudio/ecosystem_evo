# config.py
import json
from pathlib import Path
from typing import Dict


class Config:
    def __init__(self):
        self.base_path = Path(__file__).parent / "config"
       
        # ゲーム全体設定
        self.game = self._load("game.json")
       
        # ワールド設定
        self.worlds = self._load_all("worlds")
        
        # 種族設定（Speciesクラスで使用）
        self.species = self._load_all("species")

    def _load(self, filename: str) -> Dict:
        """単一のJSONファイルを読み込む"""
        path = self.base_path / filename
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def _load_all(self, folder: str) -> Dict:
        """指定フォルダ内のすべてのJSONを name をキーにして読み込む"""
        data = {}
        folder_path = self.base_path / folder
        if not folder_path.exists():
            print(f"警告: {folder_path} フォルダが見つかりません")
            return data
           
        for json_file in folder_path.glob("*.json"):
            with open(json_file, encoding='utf-8') as f:
                item = json.load(f)
                if "name" in item:
                    data[item["name"]] = item
                else:
                    print(f"警告: {json_file.name} に 'name' キーがありません")
        return data

    def get_world(self, name: str = "Grassland"):
        """ワールドデータを取得"""
        return self.worlds.get(name, self.worlds.get("Grassland"))

    def get_species(self, name: str = "Amoeba"):
        """種族データを取得（Species.createで使用）"""
        return self.species.get(name, self.species.get("Amoeba"))


# グローバルインスタンス
config = Config()