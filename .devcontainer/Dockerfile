# This repo's dev container: the shared base image (Ubuntu, AWS CLI, mise; built in
# amcaughan-personal/dev-environment) plus the tools in .tool-versions, installed by mise.
# checkov:skip=CKV_DOCKER_2:Development environment, not a long-running service
FROM ghcr.io/amcaughan-personal/devcontainer-base:latest@sha256:a2effe96ce1a2825d0b967debcd557497e18ab131cb4eca173999f0ae49a4085

COPY --chown=dev .tool-versions /tmp/tool-versions/.tool-versions
RUN cd /tmp/tool-versions && mise install && mise reshim
