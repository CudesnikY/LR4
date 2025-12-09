import time
import pika
import json
import threading
from flask import Flask, jsonify

app = Flask(__name__)

products = {
    "101": {"id": "101", "name": "3D Model Pack", "price": 10.0, "available": 5},
    "102": {"id": "102", "name": "Game Texture", "price": 5.0, "available": 10}
}


@app.route("/product/<product_id>")
def get_product(product_id):
    return jsonify(products.get(product_id, {"error": "Not found"}))


def start_consumer():

    while True:
        try:

            parameters = pika.ConnectionParameters(
                'rabbitmq', heartbeat=600, blocked_connection_timeout=300)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            try:
                channel.queue_declare(queue='orders', passive=True)
            except:

                print("Queue not found or mismatch, retrying...")
                connection.close()
                time.sleep(5)
                continue

            print("✅ Product-Service connected to RabbitMQ!")

            def callback(ch, method, properties, body):
                print(f" [x] Received {body}")
                # Імітація помилки (за завданням)
                try:
                    raise Exception("Simulated failure in product service")
                except Exception as e:
                    print(f"❌ Error processing: {e}. Sending to DLQ.")
                    ch.basic_nack(
                        delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(
                queue='orders', on_message_callback=callback, auto_ack=False)
            print("Product-Service listening for order events...")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print("⚠️ RabbitMQ not ready yet, retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ Connection lost: {e}. Retrying in 5 seconds...")
            time.sleep(5)


# Запускаємо в окремому потоці
threading.Thread(target=start_consumer, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
