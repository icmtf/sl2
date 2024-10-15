ARG REGISTRY
FROM ${REGISTRY}python:3.9-slim

WORKDIR /docs

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["mkdocs", "build", "--clean", "--site-dir", "/output"]
