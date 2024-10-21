ARG REGISTRY
FROM ${REGISTRY}python:3.9-slim

WORKDIR /app

# COPY pip.conf /etc/pip.conf
COPY s3_worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY common/pyinet ./pyinet
COPY s3_worker/settings.yaml .
COPY s3_worker/s3_worker.py .

CMD ["python", "s3_worker.py"]
