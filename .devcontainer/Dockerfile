# checkov:skip=CKV_DOCKER_2:Development environment, not a long-running service
# The development environment: open the repo in VS Code and "Reopen in Container", or
# build and run it with docker. Terraform, Terragrunt and uv come from .tool-versions (via
# mise), the same file CI and root.hcl read.
FROM ubuntu:24.04@sha256:9c7f200c07e3d4a03e7249d2c16bf66a51120fb876aa2242cf31451412543289
ENV DEBIAN_FRONTEND=noninteractive

# Every download is checked against a SHA-256 recorded here when the version was pinned.
ARG AWSCLI_VERSION=2.40.3
ARG AWSCLI_SHA256=4770c06c4ecfc8ba94b60d89e6c7018ab7ea2cf5341b1ef05f6f93c5d6e8b705
ARG SSM_PLUGIN_VERSION=1.2.896.0
ARG SSM_PLUGIN_SHA256=53f51fcc67314a4bf85888a38a3967cd41f8d0f28a60a9469a63acf935ba713e
ARG MISE_VERSION=v2026.11.8
ARG MISE_SHA256=d2d5a46f507bba772686e2c8f2316b3a4439dac49a37a30db5c0e7bb077c5431

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git jq less python3 unzip \
  && rm -rf /var/lib/apt/lists/*

# uid 1000 matches the usual host user, so mounted files stay writable. Ubuntu's image
# ships an `ubuntu` user with that uid, so it goes first.
RUN userdel -r ubuntu 2>/dev/null; useradd -ms /bin/bash -u 1000 dev

RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip" -o /tmp/awscli.zip \
  && echo "${AWSCLI_SHA256}  /tmp/awscli.zip" | sha256sum -c - \
  && unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscli.zip

RUN curl -fsSL "https://s3.amazonaws.com/session-manager-downloads/plugin/${SSM_PLUGIN_VERSION}/ubuntu_64bit/session-manager-plugin.deb" -o /tmp/ssm.deb \
  && echo "${SSM_PLUGIN_SHA256}  /tmp/ssm.deb" | sha256sum -c - \
  && dpkg -i /tmp/ssm.deb && rm -f /tmp/ssm.deb

RUN curl -fsSL "https://github.com/jdx/mise/releases/download/${MISE_VERSION}/mise-${MISE_VERSION}-linux-x64.tar.gz" -o /tmp/mise.tar.gz \
  && echo "${MISE_SHA256}  /tmp/mise.tar.gz" | sha256sum -c - \
  && tar -xzf /tmp/mise.tar.gz -C /tmp && install -m 0755 /tmp/mise/bin/mise /usr/local/bin/mise \
  && rm -rf /tmp/mise /tmp/mise.tar.gz

USER dev
ENV MISE_YES=1 \
    PATH=/home/dev/.local/share/mise/shims:$PATH

# Install the tools .tool-versions names (mise checks their checksums), so they're ready
# when the container starts.
COPY --chown=dev .tool-versions /tmp/tool-versions/.tool-versions
RUN cd /tmp/tool-versions && mise install && mise reshim && terraform version && terragrunt --version

WORKDIR /workspace
CMD ["/bin/bash"]
