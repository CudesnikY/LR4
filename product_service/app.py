import time
import pika
import json
import threading
import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
import google.generativeai as genai
from auth_middleware import token_required

# --- Observability Imports ---
from prometheus_flask_exporter import PrometheusMetrics
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

app = Flask(__name__)

# Metrics & Tracing
metrics = PrometheusMetrics(app)


def configure_tracing():
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        trace.set_tracer_provider(TracerProvider())
        otlp_exporter = OTLPSpanExporter(endpoint=os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT"), insecure=True)
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()


configure_tracing()

# Logging


class TraceIdFilter(logging.Filter):
    def filter(self, record):
        span = trace.get_current_span()
        if span and span.get_span_context().trace_id:
            record.trace_id = format(span.get_span_context().trace_id, '032x')
        else:
            record.trace_id = 'no-trace'
        return True


handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s - [trace_id=%(trace_id)s] - %(message)s'))
handler.addFilter(TraceIdFilter())
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
# ---------------------------

CORS(app, resources={r"/*": {"origins": "https://cad.kpi.ua"}})
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

products = {
    "101": {"id": "101", "name": "3D Model Pack", "price": 10.0, "available": 5},
    "102": {"id": "102", "name": "Game Texture", "price": 5.0, "available": 10}
}


@app.route("/product/<product_id>")
@token_required()
def get_product(product_id):
    app.logger.info(f"Fetching product {product_id}")
    return jsonify(products.get(product_id, {"error": "Not found"}))


def ai_process_event(body):
    prompt = f"Ти - логістичний AI. Отримано замовлення: {body}. Напиши короткий лог дій (1 речення)."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Standard processing (AI Error: {e})"


def start_consumer():
    while True:
        try:
            params = pika.ConnectionParameters(
                'rabbitmq', heartbeat=600, blocked_connection_timeout=300)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue='orders', passive=True)
            print("Product-Service connected to RabbitMQ!")

            def callback(ch, method, props, body):
                print(f" [x] Received {body}")
                log = ai_process_event(body.decode())
                print(f" AI Consumer Log: {log}")
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(
                queue='orders', on_message_callback=callback, auto_ack=False)
            channel.start_consuming()
        except Exception as e:
            print(f"Connection lost: {e}. Retrying...")
            time.sleep(5)


threading.Thread(target=start_consumer, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
