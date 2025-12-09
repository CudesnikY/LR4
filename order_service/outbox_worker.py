import pika
import json
import time
from db import get_db


def setup_rabbitmq():
    # Налаштування DLX (Dead Letter Exchange)
    params = pika.ConnectionParameters('rabbitmq')
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    # Основний Exchange та DLX Exchange
    channel.exchange_declare(
        exchange='orders_exchange', exchange_type='direct')
    channel.exchange_declare(exchange='dlx_exchange', exchange_type='direct')

    # Черга для помилкових повідомлень (DLQ)
    channel.queue_declare(queue='orders_dlq')
    channel.queue_bind(exchange='dlx_exchange',
                       queue='orders_dlq', routing_key='orders_dlq_key')

    # Основна черга з аргументами для перенаправлення в DLX при помилці
    args = {
        'x-dead-letter-exchange': 'dlx_exchange',
        'x-dead-letter-routing-key': 'orders_dlq_key'
    }
    channel.queue_declare(queue='orders', arguments=args)
    channel.queue_bind(exchange='orders_exchange',
                       queue='orders', routing_key='create_order')

    connection.close()


try:
    time.sleep(10)  # Чекаємо поки RabbitMQ завантажиться
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
            connection = pika.BlockingConnection(
                pika.ConnectionParameters('rabbitmq'))
            channel = connection.channel()

            # Публікуємо повідомлення
            channel.basic_publish(
                exchange='orders_exchange',
                routing_key='create_order',
                body=event["payload"],
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            connection.close()

            cursor.execute(
                "UPDATE outbox SET status='sent' WHERE id=?", (event["id"],))
            conn.commit()
            print(f"📤 Event sent: {event['id']}")

        except Exception as e:
            print(f"⚠️ Sending event failed: {e}")
            cursor.execute(
                "UPDATE outbox SET attempts = attempts + 1 WHERE id=?", (event["id"],))
            conn.commit()

    conn.close()
    time.sleep(3)
