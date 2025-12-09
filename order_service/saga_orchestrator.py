import time
import pika
import json
import threading
from db import get_db


def start_dlq_consumer():
    connection = None
    while not connection:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters('rabbitmq'))
        except:
            time.sleep(5)

    channel = connection.channel()
    channel.queue_declare(queue='orders_dlq')

    def callback(ch, method, properties, body):
        print(f"🔙 DLQ Received: {body}")
        data = json.loads(body)
        order_id = data.get('order_id')

        if order_id:
            conn = get_db()
            cursor = conn.cursor()
            print(
                f"🔙 Rolling back order {order_id} due to Service Failure (DLQ)")

            cursor.execute(
                "UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))

            cursor.execute(
                "UPDATE outbox SET status='failed_in_consumer' WHERE order_id=?", (order_id,))

            conn.commit()
            conn.close()

        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue='orders_dlq',
                          on_message_callback=callback, auto_ack=False)
    print("Saga Orchestrator listening on DLQ...")
    channel.start_consuming()


# Запускаємо слухача DLQ в окремому потоці
threading.Thread(target=start_dlq_consumer, daemon=True).start()


while True:
    conn = get_db()
    cursor = conn.cursor()

    # Події, які не вдалося ВІДПРАВИТИ в брокер (attempts >= 5)
    cursor.execute("""
        SELECT id, order_id FROM outbox
        WHERE attempts >= 5 AND status != 'compensated'
    """)
    failed = cursor.fetchall()

    for evt in failed:
        print(
            f"🔙 Rolling back order {evt['order_id']} due to Timeout (Sender)")

        cursor.execute(
            "UPDATE orders SET status='cancelled' WHERE id=?", (evt['order_id'],))

        cursor.execute(
            "UPDATE outbox SET status='compensated' WHERE id=?", (evt["id"],))
        conn.commit()

    conn.close()
    time.sleep(5)
