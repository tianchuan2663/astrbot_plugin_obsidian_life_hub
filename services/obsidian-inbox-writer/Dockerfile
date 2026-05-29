FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN sed -i 's@http://deb.debian.org@https://mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

COPY app ./app

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=2)); raise SystemExit(0 if data.get('ok') else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
