FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libchromaprint-tools ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 10001 ada && mkdir -p /data && chown -R ada:ada /app /data
USER ada
ENV ADA_DATA_DIR=/data ADA_DATABASE_PATH=/data/jobs.sqlite3
EXPOSE 8000
CMD ["uvicorn", "ada_backend.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
