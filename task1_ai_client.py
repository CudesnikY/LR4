import os
import json
import requests
from openai import OpenAI

# Налаштування
API_URL = "http://localhost:5003/order"
PRODUCT_URL = "http://localhost:5002/product"
# Вставте ваш ключ сюди
client = OpenAI(api_key="AIzaSyCEzVNZbzynIeA3tD8JB6UmrpQTtpBPcY8")

# --- Level 1: Guardrails (Token Expenditure) ---


class TokenGuard:
    def __init__(self, limit=1000):
        self.used = 0
        self.limit = limit

    def check(self, usage):
        if usage:
            self.used += usage.total_tokens
            print(f" Токенів використано: {self.used}/{self.limit}")
            if self.used > self.limit:
                raise Exception("Перевищено ліміт токенів!")


token_guard = TokenGuard(limit=500)

# --- Інструменти (Tools) ---


def get_product_info(product_id):
    """Отримати інформацію про продукт за ID."""
    try:
        resp = requests.get(f"{PRODUCT_URL}/{product_id}")
        return json.dumps(resp.json())
    except Exception as e:
        return json.dumps({"error": str(e)})


def create_order_tool(user_id, product_id):
    """Створити замовлення для користувача і продукту."""
    payload = {"user_id": user_id, "product_id": product_id}
    try:
        resp = requests.post(API_URL, json=payload)
        return json.dumps(resp.json())
    except Exception as e:
        return json.dumps({"error": str(e)})


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_product_info",
            "description": "Перевірити наявність та ціну товару за ID (наприклад, '101' або '102').",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_order_tool",
            "description": "Створити замовлення. Потрібно знати ID користувача та ID продукту.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "product_id": {"type": "string"}
                },
                "required": ["user_id", "product_id"]
            }
        }
    }
]

# --- Level 3: Guardrails (Prompt Injection) ---


def is_unsafe(prompt):
    forbidden = ["ignore previous instructions",
                 "system override", "delete database"]
    return any(phrase in prompt.lower() for phrase in forbidden)


def run_agent(user_prompt):
    if is_unsafe(user_prompt):
        return " Запит відхилено системою безпеки."

    messages = [
        {"role": "system", "content": "Ти помічник магазину. Ти допомагаєш створювати замовлення. ID користувача за замовчуванням '1'."},
        {"role": "user", "content": user_prompt}
    ]

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # або gpt-4
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    token_guard.check(response.usage)
    msg = response.choices[0].message

    # Обробка виклику функцій
    if msg.tool_calls:
        messages.append(msg)
        for tool_call in msg.tool_calls:
            print(f" Виклик функції: {tool_call.function.name}")

            if tool_call.function.name == "get_product_info":
                args = json.loads(tool_call.function.arguments)
                result = get_product_info(args["product_id"])
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": result
                })
            elif tool_call.function.name == "create_order_tool":
                args = json.loads(tool_call.function.arguments)
                result = create_order_tool(args["user_id"], args["product_id"])
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": result
                })

        # Другий виклик до LLM з результатами функцій
        final_resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        token_guard.check(final_resp.usage)
        return final_resp.choices[0].message.content

    return msg.content


# --- Тест (Level 2: Chaining) ---
# Запит вимагає спочатку перевірити товар (101), а потім замовити його
print("User: Хочу купити товар 101, якщо він є.")
print("AI:", run_agent(
    "Перевір товар 101 і якщо це '3D Model Pack', купи його для користувача 1."))
