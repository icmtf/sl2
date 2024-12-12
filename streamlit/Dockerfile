ARG REGISTRY
FROM ${REGISTRY}python:3.9-slim

WORKDIR /app

# COPY pip.conf /etc/pip.conf
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ENABLE_CORS=true
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false

CMD ["streamlit", "run", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.enableCORS", "true", "--server.enableXsrfProtection", "false", "app.py"]
