import pika
import json
import time
import os
from db import get_db
from openai import OpenAI

# Ініціалізація OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def setup_rabbitmq():
    params = pika.ConnectionParameters('rabbitmq')
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(
        exchange='orders_exchange', exchange_type='direct')
    channel.exchange_declare(exchange='dlx_exchange', exchange_type='direct')
    channel.queue_declare(queue='orders_dlq')
    channel.queue_bind(exchange='dlx_exchange',
                       queue='orders_dlq', routing_key='orders_dlq_key')
    args = {'x-dead-letter-exchange': 'dlx_exchange',
            'x-dead-letter-routing-key': 'orders_dlq_key'}
    channel.queue_declare(queue='orders', arguments=args)
    channel.queue_bind(exchange='orders_exchange',
                       queue='orders', routing_key='create_order')
    connection.close()


def ai_validate_order(order_data):
    """Запитуємо AI, чи виглядає замовлення підозрілим"""
    try:
        prompt = f"""
        Ти - AI-фільтр для системи замовлень. Проаналізуй це замовлення:
        {order_data}
        
        Правила:
        1. Ціна (price) має бути > 0.
        2. Якщо ціна > 100, це "high_value".
        
        Відповіж ТІЛЬКИ у форматі JSON: {{"status": "approve" | "reject", "reason": "..."}}
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        return {"status": "approve", "reason": "AI unavailable"}  # Fallback


try:
    time.sleep(10)
    setup_rabbitmq()
except Exception as e:
    print(f"RabbitMQ setup failed: {e}")

while True:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, payload FROM outbox WHERE status='pending'")
    events = cursor.fetchall()

    for event in events:
        try:
            payload_dict = json.loads(event["payload"])

            # --- AI CHECK ---
            print(f" AI Producer перевіряє замовлення {event['id']}...")
            decision = ai_validate_order(payload_dict)
            print(f" Рішення: {decision}")

            if decision.get("status") == "reject":
                print(f" Замовлення відхилено AI: {decision['reason']}")
                cursor.execute(
                    "UPDATE outbox SET status='rejected_by_ai' WHERE id=?", (event["id"],))
                conn.commit()
                continue
            # ----------------

            connection = pika.BlockingConnection(
                pika.ConnectionParameters('rabbitmq'))
            channel = connection.channel()

            channel.basic_publish(
                exchange='orders_exchange',
                routing_key='create_order',
                body=event["payload"],
                properties=pika.BasicProperties(delivery_mode=2)
            )
            connection.close()

            cursor.execute(
                "UPDATE outbox SET status='sent' WHERE id=?", (event["id"],))
            conn.commit()
            print(f" Event sent: {event['id']}")

        except Exception as e:
            print(f" Sending event failed: {e}")
            cursor.execute(
                "UPDATE outbox SET attempts = attempts + 1 WHERE id=?", (event["id"],))
            conn.commit()

    conn.close()
    time.sleep(3)
