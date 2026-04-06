# Custom n8n image for PolyTool RIS pilot
# Extends n8nio/n8n:2.14.2 with docker-cli so Execute Command nodes can
# use `docker exec polytool-ris-scheduler python -m polytool ...`
# 2.x provides instance-level MCP at /mcp-server/http (bearer token auth via N8N_MCP_BEARER_TOKEN).
FROM n8nio/n8n:2.14.2
USER root
# n8n 2.x uses Docker Hardened Image (node-based) which does not include apk or apt.
# Install docker-cli via the official Docker static binary instead.
RUN wget -q -O /tmp/docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-29.3.1.tgz \
    && tar -xz -f /tmp/docker.tgz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && chmod +x /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz
USER node
