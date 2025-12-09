from flask import Flask, jsonify, request
import requests
import json
from db import get_db, init_db

app = Flask(__name__)


@app.route("/order", methods=["POST"])
def create_order():
    data = request.json

    # Отримуємо дані від інших сервісів
    try:
        user = requests.get(
            f"http://user_service:5001/user/{data['user_id']}", timeout=5).json()
        product = requests.get(
            f"http://product_service:5002/product/{data['product_id']}", timeout=5).json()
    except Exception as e:
        return jsonify({"error": "Failed to contact dependent services"}), 503

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
    order_data['order_id'] = new_order_id  #

    cursor.execute("""
        INSERT INTO outbox (event_type, payload, order_id)
        VALUES (?, ?, ?)
    """, ("OrderCreated", json.dumps(order_data), new_order_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "Order stored and event saved to outbox", "order_id": new_order_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
