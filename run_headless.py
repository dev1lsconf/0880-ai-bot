#!/usr/bin/env python
"""
Launcher headless: mantiene el dashboard vivo indefinidamente.
pythonw run_headless.py  (sin --fg, los threads no-daemon mantienen el proceso)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp-server"))
from server import TradingMCPServer
from api.ws_server import serve_dashboard
from api.ws_server import serve_forever  # keepalive bloqueante

if __name__ == "__main__":
    srv = TradingMCPServer(broker_name=os.environ.get("BROKER", "paper"))
    port = int(os.environ.get("HTTP_PORT", 8787))
    serve_dashboard(srv, http_port=port)
    serve_forever()  # bloquea el main thread → process no muere
