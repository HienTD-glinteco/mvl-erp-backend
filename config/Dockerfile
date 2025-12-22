FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV WORKDIR=/workspace

RUN apt-get update && apt-get install -y \
    git \
    openssh-client \
    curl \
    ca-certificates \
    less \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI + Copilot
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
    https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh \
    && curl -fsSL https://gh.io/copilot-install | bash || true

# SSH known_hosts
RUN mkdir -p /root/.ssh \
    && ssh-keyscan github.com >> /root/.ssh/known_hosts \
    && chmod 600 /root/.ssh/known_hosts

WORKDIR ${WORKDIR}
CMD ["/bin/bash"]
