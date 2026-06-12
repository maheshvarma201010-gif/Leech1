FROM python:3.12-slim-bookworm

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    aria2 \
    qbittorrent-nox \
    cpulimit \
    curl \
    unzip \
    7z \
    p7zip-full \
    p7zip-rar \
    libmagic1 \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir uv && uv pip install --no-cache-dir --system -r requirements.txt

COPY . .

CMD ["bash", "start.sh"]
