import os
import json
import requests
import google.generativeai as genai
from google.api_core import retry

# Налаштування
API_URL = "http://localhost:5003/order"
PRODUCT_URL = "http://localhost:5002/product"
genai.configure(api_key="${GEMINI_API_KEY}")


def get_product_info(product_id: str):
    """Перевірити наявність та ціну товару за ID (наприклад, '101' або '102')."""
    try:
        resp = requests.get(f"{PRODUCT_URL}/{product_id}")
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def create_order_tool(user_id: str, product_id: str):
    """Створити замовлення. Потрібно знати ID користувача та ID продукту."""
    payload = {"user_id": user_id, "product_id": product_id}
    try:
        resp = requests.post(API_URL, json=payload)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


# Список інструментів для Gemini
my_tools = [get_product_info, create_order_tool]

# --- Level 3: Guardrails (Prompt Injection) ---


def is_unsafe(prompt):
    forbidden = ["ignore previous instructions",
                 "system override", "delete database"]
    return any(phrase in prompt.lower() for phrase in forbidden)


def run_agent(user_prompt):
    if is_unsafe(user_prompt):
        return " Запит відхилено системою безпеки."

    # Gemini 1.5 Flash - швидка і дешева модель
    model = genai.GenerativeModel(
        'gemini-1.5-flash',
        tools=my_tools,
        system_instruction="Ти помічник магазину. Ти допомагаєш створювати замовлення. ID користувача за замовчуванням '1'."
    )

    # Автоматичний виклик функцій спрощує код (замінює цикл обробки tool_calls)
    chat = model.start_chat(enable_automatic_function_calling=True)

    try:
        response = chat.send_message(user_prompt)

        # Перевірка токенів (проста імітація, оскільки структура usage інша)
        usage = response.usage_metadata
        print(f" Токенів використано: {usage.total_token_count}")

        return response.text
    except Exception as e:
        return f"Error: {e}"


# --- Тест ---
print("User: Хочу купити товар 101, якщо він є.")
print("AI:", run_agent(
    "Перевір товар 101 і якщо це '3D Model Pack', купи його для користувача 1."))
