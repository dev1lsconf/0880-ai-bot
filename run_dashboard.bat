@echo off
cd /d %~dp0mcp-server
python -u server.py --http 8787
