import time
import json
import random
import os
import google.generativeai as genai

# Вставте ваш ключ сюди або використовуйте os.environ
genai.configure(api_key="${GEMINI_API_KEY}")


def ai_producer_decision(order_data):
    prompt = f"""
    Ти - AI Producer. Твоя ціль - перевірити замовлення на аномалії перед відправкою.
    Дані: {json.dumps(order_data)}
    Правила: 
    1. Ціна не може бути 0 або менше.
    2. Назва продукту має бути адекватною.
    
    Відповіж тільки JSON: {{"action": "send" | "discard", "reason": "..."}}
    """

    model = genai.GenerativeModel(
        'gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
    response = model.generate_content(prompt)
    return json.loads(response.text)


def ai_consumer_decision(event_body):
    prompt = f"""
    Ти - AI Consumer. Ти отримав подію замовлення.
    Подія: {event_body}
    
    Ти маєш зіграти роль складського працівника.
    Якщо товар "Game Texture", скажи, що він віртуальний і доставка миттєва.
    Якщо "3D Model Pack", скажи, що треба підготувати архів.
    
    Відповіж коротким логом дій.
    """

    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text


def run_simulation():
    # 1. Створюємо тестові дані (як з бази даних outbox)
    orders_to_process = [
        {"order_id": 1, "product": "3D Model Pack", "price": 10.0},
        {"order_id": 2, "product": "Bad Item", "price": -5.0},  # Аномалія
        {"order_id": 3, "product": "Game Texture", "price": 5.0}
    ]

    print("---  AI Producer починає роботу ---")
    queue = []

    for order in orders_to_process:
        print(f"\nАналiз замовлення {order['order_id']}...")
        try:
            decision = ai_producer_decision(order)
            print(f"🤖 Рішення Producer: {decision}")

            if decision.get('action') == 'send':
                queue.append(order)
                print(" Відправлено в чергу (RabbitMQ)")
            else:
                print(" Відкинуто")
        except Exception as e:
            print(f"Помилка AI: {e}")

    print("\n---  AI Consumer починає роботу ---")
    for msg in queue:
        print(f"\nОтримано повідомлення: {msg}")
        try:
            log = ai_consumer_decision(str(msg))
            print(f"🤖 Дії Consumer: {log}")
        except Exception as e:
            print(f"Помилка AI: {e}")


if __name__ == "__main__":
    run_simulation()
