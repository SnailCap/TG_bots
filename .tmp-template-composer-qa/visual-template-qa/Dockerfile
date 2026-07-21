FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir .

VOLUME ["/app/data"]
STOPSIGNAL SIGTERM
CMD ["python", "-m", "visual_template_qa"]
