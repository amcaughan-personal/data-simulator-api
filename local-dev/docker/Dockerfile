# checkov:skip=CKV_DOCKER_2:Toolbox image for running Terragrunt locally, not a long-running service
FROM ubuntu:25.10@sha256:7cc5e35f6567ee8c66d2abb4aab0fd866669e6207c237c3a8f0947a5c7f17092
ENV DEBIAN_FRONTEND=noninteractive

# Pins. Every download below is checked against a SHA-256: from the publisher's SHA256SUMS
# file where one exists, otherwise recorded here when the version was pinned.
ARG TERRAFORM_VERSION=1.14.2
ARG TERRAGRUNT_VERSION=v0.94.0
ARG AWSCLI_VERSION=2.39.5
ARG AWSCLI_SHA256=fe0553306b3d001d162bc193d3b040027aab3466b9f910b50e702c122c0f3ff9
ARG SSM_PLUGIN_VERSION=1.2.896.0
ARG SSM_PLUGIN_SHA256=53f51fcc67314a4bf85888a38a3967cd41f8d0f28a60a9469a63acf935ba713e

# Basic tools
RUN apt-get update && apt-get install -y \
    apt-utils \
    ca-certificates \
    curl \
    git \
    python3 \
    unzip \
  && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -ms /bin/bash dev

# AWS CLI
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip" -o /tmp/awscliv2.zip \
  && echo "${AWSCLI_SHA256}  /tmp/awscliv2.zip" | sha256sum -c - \
  && unzip -q /tmp/awscliv2.zip -d /tmp \
  && /tmp/aws/install \
  && rm -rf /tmp/aws /tmp/awscliv2.zip

# Session Manager plugin
RUN curl -fsSL "https://s3.amazonaws.com/session-manager-downloads/plugin/${SSM_PLUGIN_VERSION}/ubuntu_64bit/session-manager-plugin.deb" \
    -o /tmp/session-manager-plugin.deb \
  && echo "${SSM_PLUGIN_SHA256}  /tmp/session-manager-plugin.deb" | sha256sum -c - \
  && dpkg -i /tmp/session-manager-plugin.deb \
  && rm -f /tmp/session-manager-plugin.deb

# Terraform
RUN cd /tmp \
  && curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
  && curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS" \
  && grep "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" "terraform_${TERRAFORM_VERSION}_SHA256SUMS" | sha256sum -c - \
  && unzip -q "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -d /usr/local/bin \
  && rm -f terraform_*

# Terragrunt
RUN cd /tmp \
  && curl -fsSLO "https://github.com/gruntwork-io/terragrunt/releases/download/${TERRAGRUNT_VERSION}/terragrunt_linux_amd64" \
  && curl -fsSLO "https://github.com/gruntwork-io/terragrunt/releases/download/${TERRAGRUNT_VERSION}/SHA256SUMS" \
  && grep " terragrunt_linux_amd64$" SHA256SUMS | sha256sum -c - \
  && install -m 0755 terragrunt_linux_amd64 /usr/local/bin/terragrunt \
  && rm -f terragrunt_linux_amd64 SHA256SUMS

USER dev
WORKDIR /workspace
CMD ["/bin/bash"]
