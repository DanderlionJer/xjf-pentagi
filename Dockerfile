ARG PROFILE=web
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    dnsutils \
    whois \
    iproute2 \
    jq \
    nmap \
    netcat-openbsd \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Extended profile: LDAP/SMB helpers (authorized internal assessment only)
ARG PROFILE
RUN if [ "$PROFILE" = "full" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
      ldap-utils \
      smbclient \
      && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip3 install --no-cache-dir --break-system-packages .

ENV PATH="/workspace/.local/bin:${PATH}"
CMD ["xjf", "--help"]
