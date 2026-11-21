# This repo's dev container: the shared base image (Ubuntu, AWS CLI, mise; built in
# amcaughan-personal/dev-environment) plus the tools in .tool-versions, installed by mise.
# checkov:skip=CKV_DOCKER_2:Development environment, not a long-running service
FROM ghcr.io/amcaughan-personal/devcontainer-base:latest@sha256:1fab4bc7e3e9642686dc3da626d7b66b7e2c32f142eb172fc82bf15d19fbc1b9

COPY --chown=dev .tool-versions /tmp/tool-versions/.tool-versions
RUN cd /tmp/tool-versions && mise install && mise reshim
