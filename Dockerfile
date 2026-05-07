FROM python:3.12-slim

LABEL mcp.server.name="io.github.gsc-em/aio-agents-mcp"
LABEL operator="GreenCore Solutions Corp."
LABEL endpoint="https://mcp.gsc-cpg.com"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY server/requirements.txt .
RUN pip install -r requirements.txt

COPY server/server.py .

EXPOSE 8000

CMD ["python", "server.py"]
