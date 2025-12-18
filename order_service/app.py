from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import os
import logging
from db import get_db, init_db
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

# 1. Prometheus Metrics
metrics = PrometheusMetrics(app)
metrics.info('app_info', 'Order Service Info', version='1.0.0')

# 2. OpenTelemetry Tracing


def configure_tracing():
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer_provider()
        otlp_exporter = OTLPSpanExporter(endpoint=os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT"), insecure=True)
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer.add_span_processor(span_processor)
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()


configure_tracing()

# 3. Structured Logging


class TraceIdFilter(logging.Filter):
    def filter(self, record):
        span = trace.get_current_span()
        if span:
            ctx = span.get_span_context()
            if ctx.trace_id:
                record.trace_id = format(ctx.trace_id, '032x')
            else:
                record.trace_id = 'no-trace'
        else:
            record.trace_id = 'no-trace'
        return True


handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - [trace_id=%(trace_id)s] - %(levelname)s - %(message)s'))
handler.addFilter(TraceIdFilter())
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# --- End Observability ---

CORS(app, resources={r"/*": {"origins": "https://cad.kpi.ua"}})


@app.route("/order", methods=["POST"])
@token_required(scope="write:orders")
def create_order():
    app.logger.info("Processing create_order request")
    data = request.json
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}

    try:
        user_resp = requests.get(
            f"http://user_service:5001/user/{data['user_id']}",
            headers=headers, timeout=5
        )
        product_resp = requests.get(
            f"http://product_service:5002/product/{data['product_id']}",
            headers=headers, timeout=5
        )

        if user_resp.status_code != 200 or product_resp.status_code != 200:
            app.logger.error("Failed to fetch dependent data")
            return jsonify({
                "error": "Failed to fetch details",
                "user_status": user_resp.status_code,
                "product_status": product_resp.status_code
            }), 400

        user = user_resp.json()
        product = product_resp.json()

    except Exception as e:
        app.logger.error(f"Error contacting services: {e}")
        return jsonify({"error": f"Failed to contact services: {str(e)}"}), 503

    order_data = {
        "user": user.get("name"),
        "product_id": product.get("id"),
        "product_name": product.get("name"),
        "price": product.get("price")
    }

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_name, product_id, product_name, price)
        VALUES (?, ?, ?, ?)
    """, (order_data["user"], order_data["product_id"], order_data["product_name"], order_data["price"]))
    new_order_id = cursor.lastrowid
    order_data['order_id'] = new_order_id

    cursor.execute("""
        INSERT INTO outbox (event_type, payload, order_id)
        VALUES (?, ?, ?)
    """, ("OrderCreated", json.dumps(order_data), new_order_id))

    conn.commit()
    conn.close()

    app.logger.info(f"Order created successfully: {new_order_id}")
    return jsonify({"status": "Order stored", "order_id": new_order_id})


@app.route("/order/<int:order_id>", methods=["GET"])
@token_required(scope="write:orders")
def get_order(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "Order not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
