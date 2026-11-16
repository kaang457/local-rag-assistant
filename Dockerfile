# syntax=docker/dockerfile:1
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src \
    DOCUMENTS_DIR=/app/documents INDEX_DIR=/app/index
WORKDIR /app

COPY requirements.txt .
# Behind a TLS-inspecting proxy or antivirus, pass its root CA:
#   docker build --secret id=ca,src=path/to/root.pem .
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then cat /etc/ssl/certs/ca-certificates.crt /run/secrets/ca > /tmp/ca.pem; export PIP_CERT=/tmp/ca.pem; fi; \
    pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY src src
COPY documents documents
COPY eval eval

RUN useradd --create-home app && mkdir -p index && chown -R app documents index eval
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
ENTRYPOINT ["python", "-m", "ragassist"]
CMD ["serve"]
