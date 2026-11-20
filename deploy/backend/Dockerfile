FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# The default matches the project's CN mirrors (see PIP_INDEX_URL); override
# with --build-arg APT_MIRROR=https://archive.ubuntu.com/ubuntu when needed.
ARG APT_MIRROR=http://mirrors.tuna.tsinghua.edu.cn/ubuntu
RUN sed -i \
        -e "s|http://archive.ubuntu.com/ubuntu|${APT_MIRROR}|g" \
        -e "s|http://security.ubuntu.com/ubuntu|${APT_MIRROR}|g" \
        /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.12 python3.12-venv python3.12-dev build-essential \
        ca-certificates tzdata curl gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor --batch --yes -o /etc/apt/keyrings/microsoft.gpg \
    && printf '%s\n' \
        'deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/edge stable main' \
        > /etc/apt/sources.list.d/microsoft-edge.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        microsoft-edge-stable xvfb x11vnc novnc websockify fonts-noto-cjk \
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
    TZ=Asia/Shanghai \
    DISPLAY=:99

COPY deploy/backend/entrypoint.sh /usr/local/bin/talentmind-entrypoint
RUN chmod 755 /usr/local/bin/talentmind-entrypoint

RUN userdel -r ubuntu 2>/dev/null || true \
    && groupdel ubuntu 2>/dev/null || true \
    && useradd -u 1000 -m talentmind \
    && mkdir -p /app/data/local /app/deploy/m2 \
    && chown -R talentmind:talentmind /app

USER talentmind
WORKDIR /app
EXPOSE 18000 6080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18000/health')"

ENTRYPOINT ["/usr/local/bin/talentmind-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000", "--workers", "1"]
