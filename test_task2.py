import subprocess
import sys
import json
import time


def test_mcp_server():
    print("Запуск перевірки MCP сервера...")

    process = subprocess.Popen(
        [sys.executable, "task2_mcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=0
    )

    print(" Сервер запущено. Відправляю запит 'initialize'...")

    # 1.  (Initialize)
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TestClient", "version": "1.0"}
        }
    }

    process.stdin.write(json.dumps(init_request) + "\n")
    process.stdin.flush()

    # Читаємо відповідь
    response = process.stdout.readline()
    if not response:
        print(" Сервер нічого не відповів.")
        return

    print(f" Відповідь сервера (Init): {response.strip()[:100]}...")

    # 2. (Initialized notification)
    process.stdin.write(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }) + "\n")
    process.stdin.flush()

    # 3. Запит списку інструментів (Tools List)
    print("🔍 Запитуємо список інструментів (tools/list)...")
    tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    process.stdin.write(json.dumps(tools_request) + "\n")
    process.stdin.flush()

    # Читаємо відповідь інструментів
    tools_response_str = process.stdout.readline()
    try:
        tools_response = json.loads(tools_response_str)
        tools = tools_response.get("result", {}).get("tools", [])

        print("\n УСПІХ! Знайдені інструменти:")
        for tool in tools:
            print(
                f" -   {tool['name']}: {tool.get('description', 'Без опису')}")

    except json.JSONDecodeError:
        print(f" Помилка читання JSON: {tools_response_str}")

    # Завершуємо
    process.terminate()


if __name__ == "__main__":
    try:
        test_mcp_server()
    except Exception as e:
        print(f" Сталася помилка: {e}")
        print("Переконайтеся, що файл 'task2_mcp_server.py' існує в цій папці.")
