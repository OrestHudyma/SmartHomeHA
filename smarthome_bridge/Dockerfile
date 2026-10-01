FROM python:3.13.7-slim-bookworm
ARG BUILD_VERSION=0.1.4
ARG BUILD_ARCH=aarch64
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.source="https://github.com/OrestHudyma/SmartHomeHA"
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY app/ /app/
COPY run.sh /run.sh
RUN chmod 755 /run.sh
CMD ["/run.sh"]
