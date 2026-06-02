# Sim層 ↔ Game層 境界独立性 — 記録と運用ガイド

**最終更新**: 2026-06-03  
**ステータス**: **完了（並行開発目標達成・追加分離は凍結）**

**目的**: Sim / Game 境界の契約・実施済み改善・凍結判断を記録する。  
**関連**: [Layer_Interfaces.md](./Layer_Interfaces.md)（契約） / [Architecture_Sim_Game_Boundary.md](./Architecture_Sim_Game_Boundary.md)（設計思想）

---

## 0. プロジェクト判断（2026-06-03）

**2-AI 並行開発に必要な境界分離は達成済み。** 以降の ISSUE-001（Sim 内 affiliation 解釈の全移管）等は、コスト対効果の観点から **意図的に凍結** する。

| 判断 | 理由 |
|------|------|
| ここで終了 | import 契約・Bridge/Events・フック除去で並行開発は可能 |
| 100% 意味論的分離は不要 | 別タイトルへの Sim 流用を目指さない限り边际効用が小さい |
| 過剰分離は避ける | ラッパー増殖・移行コストが保守性を下げる |

**新規開発ルール（凍結後）**:

- Sim 層に `from src.game` / `from src.client` を書かない（契約テストが検知）
- World へのフック属性注入を復活させない
- **新規**のゲーム固有解釈は Game 層に書く（既存 Sim 内の affiliation ヘルパーはそのまま触らなくてよい）
- Sim 変更時: `pytest tests/contracts tests/sim -m no_colony tests/game -q`

---

## 1. 評価サマリー（最終）

| 観点 | 状態 | 備考 |
|------|------|------|
| import 方向（Sim ↛ Game/Client） | ✅ 達成 | `tests/contracts/test_layer_imports.py` |
| Game → Sim 書き込み | ✅ 達成 | `SimBridge.execute` + `creature_by_id` |
| Sim → Game 通知 | ✅ 達成 | `EventBus` + `World.mark/is_affiliation_defeated` |
| World フック注入 | ✅ 除去 | `on_sim_tick` 等廃止 |
| Action 実装の Game 配置 | ✅ 達成 | Sim は `IdleLocomotionAction` のみ |
| Shelter 行動制限 | ✅ 達成 | Game `shelter_helpers` |
| SimEvent 中立化 | ✅ 達成 | コアイベントは事実のみ |
| 意味論的分離（Sim 内 affiliation 解釈ゼロ） | ⏸ 凍結 | 並行開発には不要。既存コードは維持 |
| `public.py` 集約 | ⏸ 凍結 | 任意改善 |
| Sim 単体で全 Action 実行 | ⏸ 凍結 | Game 起動時 register は現状維持 |

---

## 2. 実施済み改善（後戻し禁止）

| 項目 | 旧 | 新 |
|------|----|----|
| 敗北イベント | Sim 層 | `src/game/events.py` のみ |
| 敗北状態 | フック注入 | `World.mark/is_affiliation_defeated` |
| tick 進行 | `World.on_sim_tick` | `SimRunner._run_game_maintenance()` |
| 所属付与 | `on_creature_added` | `ensure_creature_affiliations()` |
| 避難中行動制限 | Sim `UtilityMind` + World whitelist | Game `shelter_helpers` |
| Orchestrator | World 属性注入 | `colony_session` WeakKeyDictionary |
| import 契約 | なし | `tests/contracts/test_layer_imports.py` |
| 純 Sim テスト | なし | `@pytest.mark.no_colony` |
| SimBridge API | private `_creature_by_id` (game) | `SimBridge.creature_by_id` |
| 脅威収集 | action 名ハードコード | `threat_species` param 汎用検出 |
| コア SimEvent | `affiliation_id` フィールド | 除去（Game が creature から解決） |
| 備蓄率 | `sim.affiliation_fill_ratio` | `ColonyOrchestrator.affiliation_fill_ratio` |

---

## 3. 凍結された任意改善（着手不要）

以下は **バックログとして記録のみ**。新規 AI に着手させない。

<details>
<summary>ISSUE-001〜008（参照用・クリックで展開）</summary>

#### ISSUE-001: Sim 内 affiliation / colony ドメイン（凍結）

`world_object_helpers`, `affiliation_group_helpers`, `spawn_placement` 等にゲーム寄り解釈が残る。  
**初手のみ実施**: `affiliation_fill_ratio` → Game 移行済み。残りは凍結。

#### ISSUE-002: 非公開 API 依存 — ✅ 完了

`SimBridge.creature_by_id` 公開化済み。

#### ISSUE-003: `public.py` 未整備（凍結）

Game の Sim 直 import 集約。任意。

#### ISSUE-004: Action レジストリ（凍結）

Action クラスは Game 配置済み。実行時 register は現状維持。  
エラーメッセージから `register_game_actions` 参照は除去済み。

#### ISSUE-005: ゲームコマンド型 in `sim.commands`（凍結）

`SetAffiliationCasteMind` 等。Bridge hook で動作中。

#### ISSUE-006: sim テスト bind（凍結）

`no_colony` 30 件で純 Sim 検証は可能。

#### ISSUE-007: docstring 語彙（凍結）

#### ISSUE-008: Client 直 import（凍結）

`client_api` 拡張は Client 担当時に随時。

</details>

---

## 4. 意図的な設計（削除・移動しない）

| パターン | 理由 |
|----------|------|
| `World.mark/is_affiliation_defeated` | Game 書き / Sim 読みの中立フラグ |
| `AffiliationAllAccessRemovedEvent` | 接続点全滅という物理的事実 |
| `CompoundSystem` | 汎用 storage + access |
| `colony_session` WeakKeyDictionary | Sim が Game を import しない Orchestrator 紐付け |
| `SimBridge` + `game_hooks` | Game 固有命令の委譲 |
| Game → Sim utils 直 import | 契約上許可（凍結後も維持） |
| Sim 内 affiliation ヘルパー（既存） | 凍結。新規追加のみ Game 側へ |

---

## 5. 変更時チェックリスト

```bash
python -m pytest tests/contracts -q
python -m pytest tests/sim/ -m no_colony -q
python -m pytest tests/game/ -q
```

```markdown
- [ ] Sim 層に `from src.game` / `from src.client` がない
- [ ] 新規 World フック属性を Sim に追加していない
- [ ] ゲーム専用 UI 文言を Sim に置いていない
- [ ] 契約変更時は docs/Layer_Interfaces.md を更新
```

---

## 6. 参考ファイル

| 用途 | パス |
|------|------|
| 層契約 | `docs/Layer_Interfaces.md` |
| ゲーム企画 | `docs/Game_Vision.md` |
| 設計思想 | `docs/Architecture_Sim_Game_Boundary.md` |
| Bridge | `docs/SimBridge.md` |
| イベント | `docs/Simulation_Events.md` |
| import 契約 | `tests/contracts/test_layer_imports.py` |
| Sim README | `src/sim/README.md` |

---

## 7. 変更履歴

| 日付 | 内容 |
|------|------|
| 2026-06 | 初版（Grok レビュー） |
| 2026-06-02 | ISSUE 番号付きバックログ化（Cursor） |
| 2026-06-03 | コード修正同期（creature_by_id、shelter、イベント中立化、fill_ratio 移行） |
| 2026-06-03 | **凍結判断**: 並行開発目標達成として完了。§3 を任意改善に格下げ。game_director 接続点攻撃判定修正・テスト追加 |
