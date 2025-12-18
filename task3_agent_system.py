import time
import json
import random
from openai import OpenAI

client = OpenAI(api_key="AIzaSyCEzVNZbzynIeA3tD8JB6UmrpQTtpBPcY8")

#  AI Agent Producer
# Замість простого відправлення, він аналізує, чи варто відправляти подію


def ai_producer_decision(order_data):
    prompt = f"""
    Ти - AI Producer. Твоя ціль - перевірити замовлення на аномалії перед відправкою.
    Дані: {order_data}
    Правила: 
    1. Ціна не може бути 0 або менше.
    2. Назва продукту має бути адекватною.
    
    Відповіж тільки JSON: {{"action": "send" | "discard", "reason": "..."}}
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)

#  AI Agent Consumer
# Замість простого збереження, він вирішує, як обробити


def ai_consumer_decision(event_body):
    prompt = f"""
    Ти - AI Consumer. Ти отримав подію замовлення.
    Подія: {event_body}
    
    Ти маєш зіграти роль складського працівника.
    Якщо товар "Game Texture", скажи, що він віртуальний і доставка миттєва.
    Якщо "3D Model Pack", скажи, що треба підготувати архів.
    
    Відповіж коротким логом дій.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


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
        decision = ai_producer_decision(order)
        print(f"🤖 Рішення Producer: {decision}")

        if decision['action'] == 'send':
            queue.append(order)
            print(" Відправлено в чергу (RabbitMQ)")
        else:
            print(" Відкинуто")

    print("\n---  AI Consumer починає роботу ---")
    for msg in queue:
        print(f"\nОтримано повідомлення: {msg}")
        log = ai_consumer_decision(msg)
        print(f"🤖 Дії Consumer: {log}")


if __name__ == "__main__":
    run_simulation()
