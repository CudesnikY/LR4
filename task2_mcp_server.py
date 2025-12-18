from mcp.server.fastmcp import FastMCP
import requests

# Створюємо сервер "ShopMCP"
mcp = FastMCP("ShopMCP")

ORDER_SERVICE_URL = "http://localhost:5003"
PRODUCT_SERVICE_URL = "http://localhost:5002"


@mcp.tool()
def list_products() -> str:
    """Отримати список доступних продуктів (імітація, бо API цього не має)"""
    # У реальності тут був би запит до API
    return "Доступні ID: 101 (3D Model), 102 (Texture)"


@mcp.tool()
def get_product_details(product_id: str) -> str:
    """Отримати деталі продукту за ID"""
    try:
        resp = requests.get(f"{PRODUCT_SERVICE_URL}/product/{product_id}")
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def place_order(user_id: str, product_id: str) -> str:
    """Зробити замовлення через Order Service"""
    try:
        resp = requests.post(f"{ORDER_SERVICE_URL}/order", json={
            "user_id": user_id,
            "product_id": product_id
        })
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    # Запуск сервера
    mcp.run()
