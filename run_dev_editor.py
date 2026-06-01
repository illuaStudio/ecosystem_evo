"""開発エディタ: Web 設定 UI + Pygame マップエディタ。



  python run_dev_editor.py              # API + ブラウザ + マップ

  python run_dev_editor.py --no-map     # API + ブラウザのみ

  python run_dev_editor.py --no-browser # API + マップ（ブラウザは手動で開く）

"""

from __future__ import annotations



import argparse

import json

import sys

import threading

import time

import urllib.error

import urllib.request

import webbrowser

from pathlib import Path

from typing import Any, Dict, Optional



ROOT = Path(__file__).resolve().parent

sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "tools"))



from editor_server.app import API_VERSION, DEFAULT_PORT, create_app  # noqa: E402





def _probe_health(host: str, port: int) -> Optional[Dict[str, Any]]:

    url = f"http://{host}:{port}/api/health"

    try:

        with urllib.request.urlopen(url, timeout=0.5) as resp:

            if resp.status != 200:

                return None

            raw = resp.read().decode("utf-8")

            data = json.loads(raw)

            return data if isinstance(data, dict) else None

    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):

        return None





def _health_is_current(data: Optional[Dict[str, Any]]) -> bool:

    if not data or data.get("status") != "ok":

        return False

    if int(data.get("api_version", 0)) >= API_VERSION:

        return True

    features = data.get("features") or []

    return "create" in features and "delete" in features





def _wait_for_server(host: str, port: int, timeout_sec: float = 8.0) -> bool:

    deadline = time.monotonic() + timeout_sec

    while time.monotonic() < deadline:

        if _health_is_current(_probe_health(host, port)):

            return True

        time.sleep(0.12)

    return False





def _print_port_conflict_help(port: int) -> None:

    print(

        f"\nエラー: ポート {port} では古いエディタ API が動いています。\n"

        "新規作成・削除には API の再起動が必要です。\n",

        file=sys.stderr,

    )

    print(

        "対処:\n"

        "  1. 以前起動した python / ターミナルを終了する\n"

        "  2. もう一度: python run_dev_editor.py\n"

        "  3. 別ポート: python run_dev_editor.py --port 8766\n",

        file=sys.stderr,

    )

    print(

        "プロセス確認 (PowerShell):\n"

        f"  Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue "

        "| Select-Object -ExpandProperty OwningProcess\n",

        file=sys.stderr,

    )





def _start_server(host: str, port: int) -> threading.Thread:

    import uvicorn



    app = create_app()



    def _run() -> None:

        uvicorn.run(app, host=host, port=port, log_level="warning")



    thread = threading.Thread(target=_run, daemon=True, name="editor-server")

    thread.start()

    return thread





def main() -> None:

    parser = argparse.ArgumentParser(description="Ecosystem Evo 開発エディタ")

    parser.add_argument("--host", default="127.0.0.1")

    parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    parser.add_argument("--no-browser", action="store_true", help="ブラウザを自動で開かない")

    parser.add_argument("--no-map", action="store_true", help="Pygame マップエディタを起動しない")

    args = parser.parse_args()



    host = args.host

    port = args.port

    url = f"http://{host}:{port}/"



    existing = _probe_health(host, port)

    if existing and _health_is_current(existing):

        print(f"エディタ API は既に起動しています: {url}")

    elif existing:

        _print_port_conflict_help(port)

        sys.exit(1)

    else:

        _start_server(host, port)

        if not _wait_for_server(host, port):

            stale = _probe_health(host, port)

            if stale and not _health_is_current(stale):

                _print_port_conflict_help(port)

            else:

                print(

                    f"エラー: エディタ API が起動しませんでした ({url})",

                    file=sys.stderr,

                )

            sys.exit(1)

        print(f"エディタ API を起動しました: {url}")



    print(f"設定エディタ UI: {url}")



    if not args.no_browser:

        webbrowser.open(url)



    if args.no_map:

        print("API のみ稼働中。終了するには Ctrl+C")

        try:

            while True:

                time.sleep(3600)

        except KeyboardInterrupt:

            print()

        return



    from map_editor.app import MapEditorApp  # noqa: E402



    MapEditorApp().run()





if __name__ == "__main__":

    main()

