import time
import pika
import json
import threading
import os
from flask import Flask, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

products = {
    "101": {"id": "101", "name": "3D Model Pack", "price": 10.0, "available": 5},
    "102": {"id": "102", "name": "Game Texture", "price": 5.0, "available": 10}
}


@app.route("/product/<product_id>")
def get_product(product_id):
    return jsonify(products.get(product_id, {"error": "Not found"}))


def ai_process_event(body):
    """AI вирішує, що робити з повідомленням"""
    prompt = f"""
    Ти - логістичний AI. Отримано замовлення: {body}.
    Напиши короткий, креативний лог дій для складу (1 речення).
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except:
        return "Оброблено стандартним алгоритмом."


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
                connection.close()
                time.sleep(5)
                continue

            print(" Product-Service connected to RabbitMQ!")

            def callback(ch, method, properties, body):
                print(f" [x] Received {body}")

                # --- AI PROCESSING ---
                action_log = ai_process_event(body.decode())
                print(f" AI Consumer Log: {action_log}")
                # Тут ми підтверджуємо повідомлення, бо AI його "обробив"
                ch.basic_ack(delivery_tag=method.delivery_tag)
                # ---------------------

            channel.basic_consume(
                queue='orders', on_message_callback=callback, auto_ack=False)
            channel.start_consuming()

        except Exception as e:
            print(f" Connection lost: {e}. Retrying...")
            time.sleep(5)


threading.Thread(target=start_consumer, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
