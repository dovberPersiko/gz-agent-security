import os

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("BROKER_API_URL", "http://localhost:8000")

mcp = FastMCP("mock-broker")


def _get(path: str, **params):
    resp = httpx.get(f"{BASE_URL}{path}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json: dict):
    resp = httpx.post(f"{BASE_URL}{path}", json=json, timeout=10)
    if resp.status_code >= 400:
        return {"error": resp.json().get("detail", resp.text)}
    return resp.json()


@mcp.tool()
def get_account() -> dict:
    """Get the mock account summary: cash, equity, buying power."""
    return _get("/api/account")


@mcp.tool()
def list_positions() -> list:
    """List all open positions with current market value and unrealized P/L."""
    return _get("/api/positions")


@mcp.tool()
def get_quote(symbol: str) -> dict:
    """Get a simulated current quote for a symbol (e.g. AAPL, TSLA)."""
    return _get(f"/api/quote/{symbol}")


@mcp.tool()
def list_orders(status: str = "all") -> list:
    """List orders. status: 'all', 'open', or 'filled'."""
    return _get("/api/orders", status=status)


@mcp.tool()
def place_order(symbol: str, qty: float, side: str, order_type: str = "market", limit_price: float = None) -> dict:
    """Place a simulated order. side: 'buy' or 'sell'. order_type: 'market' or 'limit'."""
    return _post("/api/orders", {
        "symbol": symbol, "qty": qty, "side": side,
        "order_type": order_type, "limit_price": limit_price,
    })


@mcp.tool()
def cancel_order(order_id: str) -> dict:
    """Cancel an open order by id (mock orders fill instantly, so this mainly applies to unfilled limit orders)."""
    resp = httpx.post(f"{BASE_URL}/api/orders/{order_id}/cancel", timeout=10)
    if resp.status_code >= 400:
        return {"error": resp.json().get("detail", resp.text)}
    return resp.json()


@mcp.tool()
def get_portfolio_history() -> list:
    """Get the equity curve over time for this mock account."""
    return _get("/api/portfolio-history")


if __name__ == "__main__":
    mcp.run()
