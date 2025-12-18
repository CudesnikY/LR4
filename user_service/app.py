from flask import Flask, jsonify
from flask_cors import CORS
from auth_middleware import token_required

app = Flask(__name__)

# Завдання 2: Дозвіл CORS для cad.kpi.ua
CORS(app, resources={r"/*": {"origins": "https://cad.kpi.ua"}})

users = {"1": {"id": "1", "name": "Andriy"}}


@app.route("/user/<user_id>")
# Завдання 3: Захист JWT та Scope [cite: 59, 60]
@token_required()
def get_user(user_id):
    return jsonify(users.get(user_id, {"error": "User not found"}))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
