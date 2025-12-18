from flask import Flask, jsonify
from flask_cors import CORS
from auth_middleware import token_required
import os
import logging

# --- Observability Imports ---
from prometheus_flask_exporter import PrometheusMetrics
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

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
users = {"1": {"id": "1", "name": "Andriy"}}


@app.route("/user/<user_id>")
@token_required()
def get_user(user_id):
    app.logger.info(f"Fetching user {user_id}")
    return jsonify(users.get(user_id, {"error": "User not found"}))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
