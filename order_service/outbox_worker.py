import pika
import json
import time
import os
import logging
from db import get_db
import google.generativeai as genai
import requests
from opentelemetry import trace, context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


class TraceIdFilter(logging.Filter):
    def filter(self, record):
        span = trace.get_current_span()
        if span and span.get_span_context().trace_id:
            record.trace_id = format(span.get_span_context().trace_id, '032x')
        else:
            record.trace_id = 'no-trace'
        return True


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbox_worker")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s - [trace_id=%(trace_id)s] - %(levelname)s - %(message)s'))
handler.addFilter(TraceIdFilter())
logger.addHandler(handler)
logger.propagate = False  # Щоб не дублювати логи

# Налаштування Tracing
if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
    trace.set_tracer_provider(TracerProvider())
    otlp_exporter = OTLPSpanExporter(endpoint=os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT"), insecure=True)
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

tracer = trace.get_tracer("outbox_worker")

# Налаштування Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))


def setup_rabbitmq():
    while True:
        try:
            params = pika.ConnectionParameters(
                'rabbitmq', heartbeat=600, blocked_connection_timeout=300)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.exchange_declare(
                exchange='orders_exchange', exchange_type='direct')
            channel.exchange_declare(
                exchange='dlx_exchange', exchange_type='direct')
            channel.queue_declare(queue='orders_dlq')
            channel.queue_bind(exchange='dlx_exchange',
                               queue='orders_dlq', routing_key='orders_dlq_key')
            args = {'x-dead-letter-exchange': 'dlx_exchange',
                    'x-dead-letter-routing-key': 'orders_dlq_key'}
            channel.queue_declare(queue='orders', arguments=args)
            channel.queue_bind(exchange='orders_exchange',
                               queue='orders', routing_key='create_order')
            connection.close()
            logger.info("RabbitMQ setup completed successfully!")
            return
        except Exception as e:
            logger.error(f"RabbitMQ setup failed: {e}. Retrying in 5s...")
            time.sleep(5)


def ai_validate_order(order_data):
    with tracer.start_as_current_span("ai_validation"):
        try:
            prompt = f"""
            Ти - AI-фільтр. Проаналізуй: {json.dumps(order_data)}
            Правила: Ціна > 0. Якщо ціна > 100, це "high_value".
            Відповіж JSON: {{"status": "approve" | "reject", "reason": "..."}}
            """
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt, generation_config={
                                              "response_mime_type": "application/json"})
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"AI Error: {e}")
            return {"status": "approve", "reason": "AI unavailable"}


setup_rabbitmq()

while True:
    with tracer.start_as_current_span("process_outbox_batch"):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, payload FROM outbox WHERE status='pending'")
        events = cursor.fetchall()

        for event in events:
            # Створюємо span для обробки конкретної події
            with tracer.start_as_current_span("process_event", attributes={"db.event_id": event["id"]}):
                try:
                    payload_dict = json.loads(event["payload"])

                    logger.info(
                        f"AI Producer перевіряє замовлення {event['id']}...")
                    decision = ai_validate_order(payload_dict)

                    if decision.get("status") == "reject":
                        logger.info(
                            f"Замовлення відхилено AI: {decision.get('reason')}")
                        cursor.execute(
                            "UPDATE outbox SET status='rejected_by_ai' WHERE id=?", (event["id"],))
                        conn.commit()
                        continue

                    connection = pika.BlockingConnection(
                        pika.ConnectionParameters('rabbitmq'))
                    channel = connection.channel()

                    # --- Inject Context into Headers ---
                    # Це найважливіша частина: ми вставляємо поточний TraceID у повідомлення RabbitMQ
                    headers = {}
                    TraceContextTextMapPropagator().inject(headers)

                    channel.basic_publish(
                        exchange='orders_exchange',
                        routing_key='create_order',
                        body=event["payload"],
                        properties=pika.BasicProperties(
                            delivery_mode=2,
                            headers=headers  # Передаємо headers з trace_id
                        )
                    )
                    connection.close()

                    cursor.execute(
                        "UPDATE outbox SET status='sent' WHERE id=?", (event["id"],))
                    conn.commit()
                    logger.info(f"Event sent: {event['id']}")

                except Exception as e:
                    # ... логування ...
                    try:
                        # Відправка в N8N при помилці (Замініть URL на свій з N8N)
                        requests.post("http://localhost:5678/webhook-test/5f4e720f-feab-479a-94a4-1d75e57624f0",
                                      json={"error": str(e), "service": "order_worker"})
                    except:
                        pass

        conn.close()
    time.sleep(3)
