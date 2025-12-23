FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV WORKDIR=/workspace

# --------------------
# System + Python
# --------------------
RUN apt-get update && apt-get install -y \
    git \
    openssh-client \
    curl \
    ca-certificates \
    less \
    build-essential \
    python3 \
    python3-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# --------------------
# GitHub CLI + Copilot
# --------------------
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
    https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh \
    && curl -fsSL https://gh.io/copilot-install | bash || true

# --------------------
# Poetry
# --------------------
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_NO_INTERACTION=1
ENV PATH="${POETRY_HOME}/bin:${PATH}"

RUN curl -sSL https://install.python-poetry.org | python3 -

# --------------------
# Workspace
# --------------------
WORKDIR ${WORKDIR}

# --------------------
# COPY ONLY dependency files
# --------------------
COPY pyproject.toml poetry.lock* ./

RUN poetry install --no-root

CMD ["/bin/bash"]
