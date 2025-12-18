FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install flask requests pika google-generativeai flask-cors prometheus-flask-exporter opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-flask opentelemetry-instrumentation-requests opentelemetry-exporter-otlp "python-jose[cryptography]"
CMD ["python", "app.py"]
