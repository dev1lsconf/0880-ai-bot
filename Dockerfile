FROM python:3.11-slim

WORKDIR /app
COPY mcp-server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY mcp-server/ /app/
COPY dashboard/ /app/dashboard/
COPY pine-templates/ /app/pine-templates/

EXPOSE 8787
CMD ["python", "server.py", "--broker", "paper", "--http", "8787"]
