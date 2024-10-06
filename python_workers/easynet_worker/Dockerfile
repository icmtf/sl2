ARG REGISTRY
FROM ${REGISTRY}python:3.9-slim

WORKDIR /app

COPY easynet_worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY common/pyinet ./pyinet
COPY easynet_worker/settings.yaml .
COPY easynet_worker/data.json .
COPY easynet_worker/easynet_worker.py .

CMD ["python", "easynet_worker.py"]
