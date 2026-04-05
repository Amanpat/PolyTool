# Custom n8n image for PolyTool RIS pilot
# Extends n8nio/n8n:1.88.0 with docker-cli so Execute Command nodes can
# use `docker exec polytool-ris-scheduler python -m polytool ...`
FROM n8nio/n8n:1.88.0
USER root
RUN apk add --no-cache docker-cli
USER node
