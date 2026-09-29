# Application image for the Subaru sensors system: the IOC and the web server
# in ONE image, because the CI pipeline builds exactly one app image per repo.
# The role is chosen at run time by the entrypoint argument:
#
#     docker run ... <image> ioc     # EPICS IOC (CA + PVA)
#     docker run ... <image> web     # FastAPI dashboard
#
# The RPM's two systemd units (deploy/*.service.in) do exactly that.
# ioc/Dockerfile and web/Dockerfile remain for the docker-compose dev setup.
FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_DIR=/var/log/app

# build-essential: pcaspy/p4p fall back to compiling from source where no
# wheel matches.
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY ioc/requirements.txt /tmp/ioc-requirements.txt
COPY web/requirements.txt /tmp/web-requirements.txt
RUN pip install --no-cache-dir -r /tmp/ioc-requirements.txt -r /tmp/web-requirements.txt && \
    rm /tmp/*-requirements.txt

COPY ioc/ /app/ioc/
COPY web/ /app/web/
COPY deploy/entrypoint.sh /usr/local/bin/subaru-sensors

# web_server.py calls os.makedirs("static") at import time. The units run the
# container --read-only, so the directory must already exist in the image.
RUN mkdir -p /app/web/static "$LOG_DIR" && \
    useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin subaru && \
    chown subaru "$LOG_DIR"
USER 10001

ENTRYPOINT ["/usr/local/bin/subaru-sensors"]
CMD ["web"]
