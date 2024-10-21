ARG REGISTRY
FROM ${REGISTRY}python:3.9-slim

WORKDIR /app

# COPY pip.conf /etc/pip.conf
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["streamlit", "run", "app.py"]
