FROM python:3.9.2-slim-buster
RUN mkdir /app && chmod 777 /app
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# Added: gcc, libssl-dev, python3-dev are required to compile cryptg and tgcrypto
# Without them, pip installs the pure-Python fallback which caps speed at ~2 Mbps
RUN apt -qq update && apt -qq install -y \
    git python3 python3-pip ffmpeg \
    gcc libssl-dev python3-dev libffi-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip3 install --no-cache-dir -r requirements.txt

# Verify crypto acceleration is active at build time
RUN python3 -c "import cryptg; print('cryptg OK')" && \
    python3 -c "import tgcrypto; print('tgcrypto OK')"

CMD ["bash","bash.sh"]
