"""FastAPI: ゲーム設定 Web エディタ + 静的 UI。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from editor_server.paths import EDITOR_WEB_DIR
from editor_server.shared_state import clear_map_selection, get_map_selection, set_map_selection
from editor_server.store import GameConfigStore, validate_object_type, validate_species

DEFAULT_PORT = 8765
API_VERSION = 2
API_FEATURES = ("catalog", "read", "write", "create", "delete")


class SaveResult(BaseModel):
    ok: bool
    errors: List[str] = []


class ValidateResult(BaseModel):
    ok: bool
    errors: List[str] = []


class MapSelectionBody(BaseModel):
    uid: Optional[str] = None
    layer: Optional[str] = None
    type_id: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None


def create_app(store: Optional[GameConfigStore] = None) -> FastAPI:
    app = FastAPI(title="Ecosystem Evo Editor", version="0.1.0")
    cfg = store or GameConfigStore()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "api_version": API_VERSION,
            "features": list(API_FEATURES),
        }

    @app.get("/api/v1/catalog")
    def catalog() -> Dict[str, Any]:
        return cfg.catalog()

    @app.get("/api/v1/species/{name}")
    def get_species(name: str) -> Dict[str, Any]:
        try:
            return cfg.load_species(name)
        except FileNotFoundError:
            raise HTTPException(404, detail=f"species not found: {name}")

    @app.put("/api/v1/species/{name}", response_model=SaveResult)
    def put_species(name: str, body: Dict[str, Any]) -> SaveResult:
        errors = cfg.save_species(name, body)
        if errors:
            return SaveResult(ok=False, errors=errors)
        return SaveResult(ok=True)

    @app.post("/api/v1/species/{name}", response_model=SaveResult)
    def post_species(
        name: str,
        body: Optional[Dict[str, Any]] = Body(default=None),
    ) -> SaveResult:
        payload = body if body else None
        errors = cfg.create_species(name, payload)
        if errors:
            return SaveResult(ok=False, errors=errors)
        return SaveResult(ok=True)

    @app.delete("/api/v1/species/{name}", response_model=SaveResult)
    def delete_species(name: str) -> SaveResult:
        errors = cfg.delete_species(name)
        if errors:
            return SaveResult(ok=False, errors=errors)
        return SaveResult(ok=True)

    @app.post("/api/v1/species/{name}/validate", response_model=ValidateResult)
    def validate_species_endpoint(name: str, body: Dict[str, Any]) -> ValidateResult:
        errors = validate_species(body, expected_name=name)
        return ValidateResult(ok=not errors, errors=errors)

    @app.get("/api/v1/object-types/{type_id}")
    def get_object_type(type_id: str) -> Dict[str, Any]:
        try:
            return cfg.load_object_type(type_id)
        except FileNotFoundError:
            raise HTTPException(404, detail=f"object type not found: {type_id}")

    @app.put("/api/v1/object-types/{type_id}", response_model=SaveResult)
    def put_object_type(type_id: str, body: Dict[str, Any]) -> SaveResult:
        errors = cfg.save_object_type(type_id, body)
        if errors:
            return SaveResult(ok=False, errors=errors)
        return SaveResult(ok=True)

    @app.post("/api/v1/object-types/{type_id}", response_model=SaveResult)
    def post_object_type(
        type_id: str,
        body: Optional[Dict[str, Any]] = Body(default=None),
    ) -> SaveResult:
        payload = body if body else None
        errors = cfg.create_object_type(type_id, payload)
        if errors:
            return SaveResult(ok=False, errors=errors)
        return SaveResult(ok=True)

    @app.delete("/api/v1/object-types/{type_id}", response_model=SaveResult)
    def delete_object_type(type_id: str) -> SaveResult:
        errors = cfg.delete_object_type(type_id)
        if errors:
            return SaveResult(ok=False, errors=errors)
        return SaveResult(ok=True)

    @app.post("/api/v1/object-types/{type_id}/validate", response_model=ValidateResult)
    def validate_object_type_endpoint(type_id: str, body: Dict[str, Any]) -> ValidateResult:
        errors = validate_object_type(body, expected_id=type_id)
        return ValidateResult(ok=not errors, errors=errors)

    @app.get("/api/v1/map/selection")
    def map_selection_get() -> Dict[str, Any]:
        return get_map_selection()

    @app.post("/api/v1/map/selection")
    def map_selection_post(body: MapSelectionBody) -> Dict[str, Any]:
        return set_map_selection(
            uid=body.uid,
            layer=body.layer,
            type_id=body.type_id,
            x=body.x,
            y=body.y,
        )

    @app.delete("/api/v1/map/selection")
    def map_selection_delete() -> Dict[str, str]:
        clear_map_selection()
        return {"status": "cleared"}

    static_dir = EDITOR_WEB_DIR / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    index_path = EDITOR_WEB_DIR / "index.html"

    @app.get("/")
    def index() -> FileResponse:
        if not index_path.is_file():
            raise HTTPException(404, detail="editor_web/index.html missing")
        return FileResponse(index_path)

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    *,
    log_level: str = "warning",
) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port, log_level=log_level)
