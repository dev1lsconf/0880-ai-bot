#!/usr/bin/env python
"""Servidor 0880 AI BOT: levanta HTTP + WS en puertos configurables."""
import sys, os, threading, time
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from server import TradingMCPServer
from api.ws_server import _http_server, _ws_server

if __name__ == "__main__":
    port = int(os.environ.get("HTTP_PORT", 8787))
    srv = TradingMCPServer(broker_name=os.environ.get("BROKER", "paper"))
    threading.Thread(target=_http_server, args=(srv, port), daemon=False).start()
    threading.Thread(target=_ws_server, args=(srv, port + 1), daemon=True).start()
    print(f"[0880] HTTP -> http://127.0.0.1:{port}", flush=True)
    print(f"[0880] WS   -> ws://127.0.0.1:{port+1}/ws", flush=True)
    while True:
        time.sleep(3600)
