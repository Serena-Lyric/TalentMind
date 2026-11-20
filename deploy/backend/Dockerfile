FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.12 python3.12-venv python3.12-dev build-essential \
        ca-certificates tzdata curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
COPY backend/app ./app
COPY frontend/bridge-extension/manifest.json /app/frontend/bridge-extension/manifest.json
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5
RUN python3.12 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/backend \
    PYTHONUTF8=1 \
    LANG=C.UTF-8 \
    TZ=Asia/Shanghai

RUN userdel -r ubuntu 2>/dev/null || true \
    && groupdel ubuntu 2>/dev/null || true \
    && useradd -u 1000 -m talentmind \
    && mkdir -p /app/data/local /app/deploy/m2 \
    && chown -R talentmind:talentmind /app

USER talentmind
WORKDIR /app
EXPOSE 18000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000", "--workers", "1"]
