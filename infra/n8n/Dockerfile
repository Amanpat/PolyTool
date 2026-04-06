# Custom n8n image for PolyTool RIS pilot
# Extends n8nio/n8n:1.123.28 with docker-cli so Execute Command nodes can
# use `docker exec polytool-ris-scheduler python -m polytool ...`
FROM n8nio/n8n:1.123.28
USER root
# n8n 1.123.28 uses Docker Hardened Image (Alpine 3.22) which removes the apk binary.
# Install docker-cli via the official Docker static binary instead.
RUN wget -q -O /tmp/docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-29.3.1.tgz \
    && tar -xz -f /tmp/docker.tgz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && chmod +x /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz
USER node
