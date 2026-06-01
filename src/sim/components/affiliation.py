"""中立な社会的所属（affiliation）・役割・タグ。

colony はゲーム固有の語彙になりやすいので、シミュ層ではより一般的な
affiliation / squad / roles / tags を提供する。
"""

from __future__ import annotations


class AffiliationComponent:
    """社会的所属。

    - affiliation_id: 所属グループ（勢力・群れ・チーム等）の ID
    - squad_id: 所属内のサブグループ（分隊・班等）
    - roles: 行動上の役割ラベル（worker/scout/healer 等）
    - tags: 任意のメタラベル（検索・ルール適用の入口）
    """

    def __init__(
        self,
        affiliation_id: str | None = None,
        *,
        squad_id: str | None = None,
        roles: set[str] | None = None,
        tags: set[str] | None = None,
    ) -> None:
        self.affiliation_id: str | None = affiliation_id
        self.squad_id: str | None = squad_id
        self.roles: set[str] = set(roles or ())
        self.tags: set[str] = set(tags or ())

    def has_role(self, role: str) -> bool:
        return str(role) in self.roles

    def add_role(self, role: str) -> None:
        r = str(role).strip()
        if r:
            self.roles.add(r)

    def remove_role(self, role: str) -> None:
        self.roles.discard(str(role))

    def has_tag(self, tag: str) -> bool:
        return str(tag) in self.tags

    def add_tag(self, tag: str) -> None:
        t = str(tag).strip()
        if t:
            self.tags.add(t)

    def remove_tag(self, tag: str) -> None:
        self.tags.discard(str(tag))

