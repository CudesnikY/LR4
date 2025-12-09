from flask import Flask, jsonify

app = Flask(__name__)

users = {"1": {"id": "1", "name": "Andriy"}}


@app.route("/user/<user_id>")
def get_user(user_id):
    return jsonify(users.get(user_id, {"error": "User not found"}))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
