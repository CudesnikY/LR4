from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
from db import get_db, init_db
from auth_middleware import token_required

app = Flask(__name__)

# Завдання 2: CORS
CORS(app, resources={r"/*": {"origins": "https://cad.kpi.ua"}})


@app.route("/order", methods=["POST"])
# Завдання 3: Захист для запису даних
@token_required(scope="write:orders")
def create_order():
    data = request.json

    # --- ВАЖЛИВО: Отримуємо токен з поточного запиту ---
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}

    # Отримуємо дані від інших сервісів, ПЕРЕДАЮЧИ токен далі
    try:
        # Додаємо headers=headers у запити
        user_resp = requests.get(
            f"http://user_service:5001/user/{data['user_id']}",
            headers=headers,
            timeout=5
        )
        product_resp = requests.get(
            f"http://product_service:5002/product/{data['product_id']}",
            headers=headers,
            timeout=5
        )

        # Перевіряємо статус коди внутрішніх запитів
        if user_resp.status_code != 200 or product_resp.status_code != 200:
            return jsonify({
                "error": "Failed to fetch details from dependent services",
                "user_service_status": user_resp.status_code,
                "product_service_status": product_resp.status_code
            }), 400

        user = user_resp.json()
        product = product_resp.json()

    except Exception as e:
        return jsonify({"error": f"Failed to contact dependent services: {str(e)}"}), 503

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

    return jsonify({"status": "Order stored and event saved to outbox", "order_id": new_order_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
