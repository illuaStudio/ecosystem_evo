# Client層 と Game層 の並行開発境界（異なるAI向け）

**目的**: 異なるAI（例: Client担当AI と Game担当AI、または CursorAI）がそれぞれの層を触っても、互いの変更で簡単に壊れない状態にする。
Client担当は Game の内部実装を知らなくてよい。
Game担当は Client のUI詳細を知らなくてよい。

**関連ドキュメント**:
- [Layer_Interfaces.md](./Layer_Interfaces.md)（全体契約）
- [REVIEW_Sim_Game_Layer_Independence_Problems.md](./REVIEW_Sim_Game_Layer_Independence_Problems.md)
- [Game_Vision.md](./Game_Vision.md)（3フェーズなど）

**境界分離の現状（このドキュメント作成時点）**: Client と Game の間の主なファサードは `src/game/client_api.py` と `GameController` / `GameState` / `GameMessage` の公開面。

---

## 現在オープンな Client からの Game層への依頼（Game担当AI 向け）

このセクションは Client担当が Game 側の変更を依頼するときに追記・更新する。

**現在対応をお願いしているもの**: なし

**直近で完了した依頼**:

- **Hunt / Combat ターゲットの安全ビュー** — ✅ Game 実装済み（2026-06）  
  - 依頼: [Request_Game_Add_TargetView_API_for_Client_HuntOverlays.md](./Request_Game_Add_TargetView_API_for_Client_HuntOverlays.md)  
  - Game 回答・Client 移行ガイド: [Response_Game_TargetView_API_for_Client.md](./Response_Game_TargetView_API_for_Client.md)  
  - 実装: `src/game/client_api.py` の `TargetView`, `get_hunt_target_view`, `get_combat_target_view`, `get_aggression_target_view`  
  - Client: `renderer.py` をビュー使用に移行済み（ワークアラウンド撤去）

他の依頼が出たらここに追記（短い説明 + 詳細ドキュメントへのリンク）。

---

## 1. Client担当AI が Game層に触るときのルール（厳守）

Clientコード（`src/client/`）は以下の**公開APIのみ**を直接 import して使用すること。

### 推奨・許可される import（Client → Game）
```python
from src.game import client_api
from src.game.game_controller import GameController
from src.game.game_state import GameState
from src.game.game_message import GameMessage
from src.game.sim_runner import SimRunner   # メインループの tick 制御用（限定的）
```

- **colony / 勢力データ** は必ず `client_api.try_get_colony_orchestrator(world)` を経由。
  ```python
  orch = client_api.try_get_colony_orchestrator(world)
  if orch is not None:
      root = orch.get_affiliation_root(aff_id)
      fill = orch.affiliation_fill_ratio(aff_id)
      # ...
  ```
  **絶対に直接** `from src.game.colony_session import get_colony_orchestrator` や `try_get_colony_orchestrator` を書かない。

- **フェーズ・ウェーブ・ストーリー情報**:
  ```python
  view = client_api.get_phase_view(controller, world)
  if not client_api.should_advance_sim(controller):
      ...
  client_api.acknowledge_story(controller)
  client_api.request_start_defense(controller)
  ```

- **その他 Client 向けユーティリティ**:
  - `client_api.get_defeated_affiliation_ids(world)`
  - `client_api.try_get_affiliation_fill_ratio(world, id)`
  - `client_api.find_queen_reproduction_action(queen)`
  - `client_api.get_queen_reproduction_readiness(queen)`
  - `client_api.try_spawn_position(...)`

- **World の読み取り**（描画用）は許可（安定した公開属性: creatures, position など）。ただし game専用解釈（affiliation root の意味など）は client_api や orch 経由。

### 禁止・非推奨（Client → Game 内部）
- `from src.game.colony_session import ...` （直接）
- `from src.game.ai.* import ...` （Action 実装クラスなど。ラベル文字列だけはOK）
- `from src.game.colony_orchestrator import ColonyOrchestrator` （型ヒント以外で直接）
- `from src.game.colony_compound import ...`
- `from src.game.game_director import ...` （内部ロジック）
- など。新しいデータが必要になったら **client_api.py に追加を依頼**（または自分で追加して Game側に最小実装）。

**違反すると**: Game側で orchestrator の保持方法を変えたり、AI実装をリファクタすると Client が即死ぬ。並行開発が破綻する。

---

## 2. Game担当AI が Client層に影響を与えるときのルール

**Game担当AIは `src/client/` を編集しない。** Client への反映（`renderer.py` のビュー移行など）は Client担当AI が行う。Game側は `client_api`・`GameController` 等の公開面と、Client向け回答ドキュメント（例: `docs/Response_Game_*.md`）までとする。

Gameコードを変更する際は、**Client が依存している公開面を壊さない**。

### Client が依存している公開面（主なもの）
- `src/game/client_api.py` の全関数・クラス（特に `try_get_colony_orchestrator`, `get_phase_view`, 新規追加ヘルパー）
- `GameController` の公開メソッド（`on_tick`, `reset_for_world`, `spawn_creature`, `state`, `pending_messages` など）
- `GameState` のフラグ・公開属性
- `GameMessage`
- `SimRunner` の tick 制御インターフェース

### 変更時の手順（Game担当AI）
1. 内部実装（colony_orchestrator の private, game.ai 詳細など）は自由に変えてよい。
2. **公開シグネチャを変える場合**:
   - client_api に新しい関数を追加して後方互換を保つ（可能なら）。
   - または、Client担当AIに「この関数を更新して」と伝える（このドキュメント経由やPRコメント）。
3. Client が必要とする新しいデータ（例: 新しいHUD項目、突然変異表示、文明レベル詳細）は **client_api.py に追加** して実装。
   - 関数本体では Game 内部を自由に使ってよい。
   - 戻り値はシンプルな dataclass や tuple / dict に（Client が実装詳細に依存しない）。
4. テスト: `python -m pytest tests/game/ -q` と `python -m pytest tests/client/ -q` を実行。
5. 可能なら `tests/contracts -q` も。

**Client担当AIへの影響を最小化するための推奨**:
- 新しい colony データが必要 → client_api に `get_xxx_for_client(world, aff_id)` を追加。
- 女王や個体の game 状態が必要 → client_api に専用ビュー関数を追加（repro readiness のように）。

---

## 3. 実装上の推奨パターン（この分離作業後）

- Client 内のローカル `def colony(world): ...` ヘルパーはすべて `client_api.try_get_colony_orchestrator` に委譲。
- 複雑な game 解釈ロジック（女王の産卵可否計算、特定のHUDデータ集計など）は Client コードに書かず、client_api に移動。
- 描画で大量に必要なデータは、必要に応じて client_api に `get_render_view_for_affiliation(...)` のようなバッチ関数を追加検討。
- メインループの配線（World作成、SimBridge、GameController 初期化）は現在 app.py にあるが、将来的には game 側に `create_game_session()` みたいなファクトリを置いて Client はそれだけ呼ぶ形にできる（低優先）。

---

## 4. 現在の分離状況（このドキュメント作成時）

このドキュメント作成に伴い、以下の改善を実施：
- `src/client/` 内の全 `from src.game.colony_session import ...` を排除。すべて `from src.game import client_api` + `try_get_colony_orchestrator` 経由に統一。
- `queen_status.py` が直接 `src.game.ai.reproduction_actions` を import していたのを廃止。`client_api.find_queen_reproduction_action` / `get_queen_reproduction_readiness` に隠蔽。
- `client_api.py` に Client/Game 並行開発用のコメントと新ヘルパー関数を追加。
- 各 Client ファイルに「Client から Game データにアクセスする際は client_api 経由」というコメントを追加（将来のAIへの注意喚起）。
- `tests/contracts/test_layer_imports.py` に Client 並行開発ルール違反検知テストを追加（colony_session や game.ai.reproduction_actions の直接 import を検出）。

残っている直接依存（主に Sim 側、許容範囲内）:
- 描画ヘルパー（`entity_xy`, `is_creature_sheltered` など安定したもの）
- `World` オブジェクトの反復と基本属性読み取り（Layer_Interfaces で明示許可）
- `src.sim.utils.hunt_helpers` の **`find_attackers_for_target`**、攻撃者の戦闘同一性判定用 **`get_combat_target`**（renderer）。狩り/戦闘ターゲットの HUD・オーバーレイは **`client_api.get_*_target_view`** 経由。

**client_api の現在の主な公開（Client 向け）**:
- GamePhaseView / get_phase_view
- should_advance_sim / acknowledge_story / request_start_defense
- try_get_colony_orchestrator
- get_defeated_affiliation_ids
- try_get_affiliation_fill_ratio
- try_spawn_position
- find_queen_reproduction_action
- get_queen_reproduction_readiness
- TargetView / get_hunt_target_view / get_combat_target_view / get_aggression_target_view
- （今後も Client が必要とするものをここに集約）

---

## 5. チェックリスト（AI が作業するときに使う）

### Client担当AI がコードを触るとき
- [ ] `from src.game.colony_session` や `from src.game.ai.*` （Action実装）を使っていない
- [ ] colony データは `client_api.try_get_colony_orchestrator(...)` 経由
- [ ] 新しい Game データが必要になったら、まず client_api に追加を検討。このドキュメントの「現在オープンな Client からの Game層への依頼」セクションに短く追記し、詳細は別ドキュメント（例: Request_*.md）を作成してリンクを貼る。
- [ ] `python -m pytest tests/client/ -q` と `python -m pytest tests/contracts -q` を実行
- [ ] このドキュメントや Layer_Interfaces を更新（必要なら）

### Game担当AI が Client に影響する変更をするとき
- [ ] client_api の既存関数のシグネチャ・意味を壊していない
- [ ] Client がよく使う colony メソッドを直接触らせたい場合 → client_api に薄いラッパー/ビュー関数を追加
- [ ] `python -m pytest tests/game/ -q` + Client 側のテストも意識
- [ ] 変更内容をこのドキュメントの「変更履歴」または別PR説明に記載

---

## 6. 変更履歴

| 日付 | 内容 |
|------|------|
| 2026-06 | 初版作成。Client と Game の境界を「異なるAIが並行開発可能」レベルまで強化。colony_session 直接依存の排除、repro action の隠蔽、client_api 拡張、専用ドキュメント作成。 |
| 2026-06 (追加) | Hunt/Combat target の creature/WorldObject 混在により Client 描画で .species エラー発生。Client 側で defensive workaround を入れたが、設計上 `docs/Request_Game_Add_TargetView_API_for_Client_HuntOverlays.md` を作成して Game 側に `TargetView` + client_api ヘルパーの追加を正式依頼。 |
| 2026-06 (完了) | Game: `TargetView` + `get_*_target_view` を `client_api` に追加。テスト `tests/game/test_client_api_target_view.py`。Client: `renderer.py` 移行。回答 doc: `docs/Response_Game_TargetView_API_for_Client.md`。 |

---

**次のステップ提案**:
- Client がさらに必要とするデータを client_api に追加（例: 穴配置UI用のデータ、突然変異表示、詳細なコロニー統計など）。
- 可能なら `tests/client/` に「悪い import を検知する」簡易チェックを追加（ast 解析で colony_session などを禁止）。
- Game_Vision の未実装部分（フェーズ制御の強化、ウェーブなど）を実装する際は、必ず client_api を通して Client が見える形にする。

このドキュメントを参照しながら、Client担当AI と Game担当AI が独立して作業を進められる状態を目指します。