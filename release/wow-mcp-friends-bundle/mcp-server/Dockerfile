FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY wow_mcp_server /app/wow_mcp_server

RUN pip install --no-cache-dir .

ENTRYPOINT ["wow-mcp-server"]
