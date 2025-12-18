from functools import wraps
from flask import request, jsonify
from jose import jwt
from urllib.request import urlopen
import json

# Конфігурація Keycloak (зміни realm_name на свій, якщо буде інший)
KEYCLOAK_URL = "http://keycloak:8080/realms/MyRealm"
ALGORITHMS = ["RS256"]


def get_public_key():
    try:
        # Отримуємо публічні ключі з Keycloak
        json_url = urlopen(f"{KEYCLOAK_URL}/protocol/openid-connect/certs")
        jwks = json.loads(json_url.read())
        return jwks
    except Exception as e:
        print(f"Error fetching public key: {e}")
        return None


def verify_token(token, required_scope=None):
    jwks = get_public_key()
    if not jwks:
        return {"error": "Auth server unavailable"}

    unverified_header = jwt.get_unverified_header(token)
    rsa_key = {}

    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }

    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience="account",  # Стандартна аудиторія Keycloak
                options={"verify_at_hash": False}
            )

            # Перевірка Scope (завдання 3c)
            if required_scope:
                token_scopes = payload.get("scope", "").split()
                if required_scope not in token_scopes:
                    return {"error": "Insufficient scope"}

            return payload
        except jwt.ExpiredSignatureError:
            return {"error": "Token is expired"}
        except jwt.JWTClaimsError:
            return {"error": "Incorrect claims"}
        except Exception:
            return {"error": "Unable to parse authentication token"}

    return {"error": "Unable to find appropriate key"}


def token_required(scope=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None

            # Очікуємо заголовок Authorization: Bearer <token>
            if 'Authorization' in request.headers:
                auth_header = request.headers['Authorization']
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]

            if not token:
                return jsonify({'message': 'Token is missing!'}), 401

            validation = verify_token(token, scope)
            if "error" in validation:
                return jsonify({'message': validation["error"]}), 401

            # Можна передати дані користувача в функцію
            # current_user = validation
            return f(*args, **kwargs)
        return decorated
    return decorator
