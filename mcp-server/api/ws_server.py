"""
Servidor HTTP (estatico + API) y WebSocket unificado - puerto unico.
- GET / ........................ dashboard/index.html
- GET /api/snapshot ............ JSON snapshot (refresh)
- WS  /ws .................... streaming snapshot (cada ~3s)
Uso: python run_headless.py
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import threading

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DASH_DIR = os.path.join(ROOT, "dashboard")


def _snapshot(server) -> dict:
    from server import _build_snapshot
    return _build_snapshot(server)


STATIC_TYPES = {
    "/index.html": "text/html", "/": "text/html",
    "/style.css": "text/css", "/app.js": "application/javascript",
}


def _http_server(server, port: int):
    """Servidor HTTP estatico + API. Bloqueante - thread no-daemon."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/snapshot":
                self._send(200, json.dumps(_snapshot(server)).encode(), "application/json")
                return
            ctype = STATIC_TYPES.get(path, mimetypes.guess_type(path)[0] or "application/octet-stream")
            fname = "index.html" if path == "/" else path.lstrip("/")
            fpath = os.path.normpath(os.path.join(DASH_DIR, fname))
            if not fpath.startswith(DASH_DIR) or not os.path.isfile(fpath):
                self._send(404, b"not found", "text/plain")
                return
            with open(fpath, "rb") as f:
                self._send(200, f.read(), ctype)

        do_HEAD = do_GET

        def do_POST(self):
            """Ejecuta acciones en el broker (place_order / close_position)."""
            import json as _json
            try:
                ln = int(self.headers.get("Content-Length", 0) or 0)
                body = _json.loads(self.rfile.read(ln).decode() or "{}") if ln else {}
            except Exception:
                body = {}
            action = body.get("action")
            try:
                if action == "place_order":
                    broker = server.broker
                    res = broker.place_order(
                        symbol=body.get("symbol", ""),
                        asset_class=body.get("asset_class", "CRYPTO"),
                        side=body.get("side", "BUY"),
                        qty=float(body.get("qty", 1)),
                    )
                    self._send(200, _json.dumps({"ok": True, "result": str(res)}).encode(), "application/json")
                elif action == "close_position":
                    broker = server.broker
                    res = broker.close_position(symbol=body.get("symbol", ""))
                    self._send(200, _json.dumps({"ok": True, "result": str(res)}).encode(), "application/json")
                else:
                    self._send(400, _json.dumps({"ok": False, "error": "accion desconocida"}).encode(), "application/json")
            except Exception as e:
                self._send(500, _json.dumps({"ok": False, "error": str(e)}).encode(), "application/json")

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    httpd.serve_forever()


def _ws_server(server, port: int):
    """Servidor WebSocket streaming. Bloqueante - thread async."""
    import websockets

    async def ws_handler(ws):
        try:
            async with ws:
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        if isinstance(msg, str) and msg.strip() == "refresh":
                            await ws.send(json.dumps({"type": "snapshot", "data": _snapshot(server)}))
                            continue
                        # msg recibido pero no es refresh -> sigue al snapshot push
                    except asyncio.TimeoutError:
                        pass
                    except Exception:
                        break
                    try:
                        await ws.send(json.dumps({"type": "snapshot", "data": _snapshot(server)}))
                    except Exception:
                        break
        except Exception:
            pass

    async def ws_main():
        async with websockets.serve(ws_handler, "127.0.0.1", port,
                                    max_size=8 * 1024 * 1024, ping_interval=20, ping_timeout=30):
            await asyncio.Future()

    try:
        asyncio.run(ws_main())
    except OSError as e:
        print(f"[dashboard] WS no iniciado en {port}: {e}", flush=True)


def serve_dashboard(server, http_port: int = 8787, ws_port: int | None = None):
    """Lanza HTTP (thread no-daemon) + WS (thread daemon)."""
    ws_port = ws_port or http_port + 1
    threading.Thread(target=_http_server, args=(server, http_port), daemon=False).start()
    threading.Thread(target=_ws_server, args=(server, ws_port), daemon=True).start()
    print(f"[dashboard] HTTP -> http://127.0.0.1:{http_port}", flush=True)
    print(f"[dashboard] WS   -> ws://127.0.0.1:{ws_port}/ws", flush=True)
    print(f"[dashboard] MCP  -> stdio (stdin)", flush=True)


def serve_forever() -> None:
    """Bloquea el main thread para mantener HTTP/WS vivos."""
    import time
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    from server import TradingMCPServer
    srv = TradingMCPServer(broker_name="paper")
    serve_dashboard(srv, http_port=args.port)
    serve_forever()