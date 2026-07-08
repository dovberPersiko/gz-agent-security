import json
import os
import random
import threading
import time
import uuid
from pathlib import Path

STATE_FILE = Path(__file__).parent / "data" / "state.json"
_lock = threading.Lock()

SEED_PRICES = {
    "AAPL": 232.50,
    "MSFT": 428.30,
    "TSLA": 251.80,
    "NVDA": 138.20,
    "SPY": 561.40,
    "GOOGL": 176.90,
    "AMZN": 198.40,
}

FRAUD_REVIEW_QTY_THRESHOLD = 3


def _new_state():
    state = {
        "cash": 100000.0,
        "positions": {},
        "orders": [],
        "prices": dict(SEED_PRICES),
        "price_updated_at": time.time(),
        "equity_history": [{"t": time.time(), "equity": 100000.0}],
    }
    for symbol, qty in (("AAPL", 40), ("MSFT", 20), ("TSLA", 15)):
        price = state["prices"][symbol]
        state["cash"] -= qty * price
        state["positions"][symbol] = {"qty": qty, "avg_entry_price": price}
    return state


def load_state():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    state = _new_state()
    save_state(state)
    return state


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, STATE_FILE)


def drift_prices(state):
    now = time.time()
    elapsed = now - state["price_updated_at"]
    if elapsed < 1:
        return state
    for symbol, price in state["prices"].items():
        volatility = 0.0015
        shock = random.gauss(0, volatility) * min(elapsed / 60, 30) ** 0.5
        state["prices"][symbol] = round(max(price * (1 + shock), 0.01), 2)
    state["price_updated_at"] = now
    return state


def equity(state):
    total = state["cash"]
    for symbol, pos in state["positions"].items():
        total += pos["qty"] * state["prices"].get(symbol, pos["avg_entry_price"])
    return round(total, 2)


def record_equity(state):
    state["equity_history"].append({"t": time.time(), "equity": equity(state)})
    state["equity_history"] = state["equity_history"][-500:]


def get_account():
    with _lock:
        state = drift_prices(load_state())
        result = {
            "cash": round(state["cash"], 2),
            "equity": equity(state),
            "buying_power": round(state["cash"] * 2, 2),
            "currency": "USD",
            "mode": "paper",
        }
        save_state(state)
        return result


def list_positions():
    with _lock:
        state = drift_prices(load_state())
        result = []
        for symbol, pos in state["positions"].items():
            price = state["prices"].get(symbol, pos["avg_entry_price"])
            market_value = round(pos["qty"] * price, 2)
            cost_basis = pos["qty"] * pos["avg_entry_price"]
            result.append({
                "symbol": symbol,
                "qty": pos["qty"],
                "avg_entry_price": pos["avg_entry_price"],
                "current_price": price,
                "market_value": market_value,
                "unrealized_pl": round(market_value - cost_basis, 2),
                "unrealized_pl_pct": round((market_value - cost_basis) / cost_basis * 100, 2) if cost_basis else 0,
            })
        save_state(state)
        return result


def get_quote(symbol):
    with _lock:
        state = load_state()
        symbol = symbol.upper()
        if symbol not in state["prices"]:
            state["prices"][symbol] = round(random.uniform(20, 400), 2)
        state = drift_prices(state)
        save_state(state)
        return {"symbol": symbol, "price": state["prices"][symbol]}


def list_symbols():
    with _lock:
        state = load_state()
        return sorted(state["prices"].keys())


def list_orders(status="all"):
    with _lock:
        state = load_state()
        orders = state["orders"]
        if status != "all":
            orders = [o for o in orders if o["status"] == status]
        return list(reversed(orders))


def _execute_fill(state, order):
    symbol = order["symbol"]
    qty = order["qty"]
    fill_price = order["fill_price"]
    pos = state["positions"].get(symbol, {"qty": 0, "avg_entry_price": 0})
    if order["side"] == "buy":
        cost = qty * fill_price
        if cost > state["cash"]:
            order["status"] = "rejected"
            order["reason"] = "insufficient buying power"
        else:
            new_qty = pos["qty"] + qty
            pos["avg_entry_price"] = round((pos["qty"] * pos["avg_entry_price"] + cost) / new_qty, 4) if new_qty else 0
            pos["qty"] = new_qty
            state["cash"] -= cost
            state["positions"][symbol] = pos
            order["status"] = "filled"
    else:
        if pos["qty"] < qty:
            order["status"] = "rejected"
            order["reason"] = "insufficient position size"
        else:
            pos["qty"] -= qty
            state["cash"] += qty * fill_price
            if pos["qty"] <= 0:
                state["positions"].pop(symbol, None)
            else:
                state["positions"][symbol] = pos
            order["status"] = "filled"
    record_equity(state)
    return order


def place_order(symbol, qty, side, order_type="market", limit_price=None):
    with _lock:
        state = drift_prices(load_state())
        symbol = symbol.upper()
        side = side.lower()
        if symbol not in state["prices"]:
            return {"error": f"unknown symbol {symbol}"}
        if side not in ("buy", "sell"):
            return {"error": "side must be 'buy' or 'sell'"}
        if qty <= 0:
            return {"error": "qty must be positive"}

        fill_price = limit_price if order_type == "limit" and limit_price else state["prices"][symbol]
        order = {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "limit_price": limit_price,
            "status": "pending_confirmation",
            "fill_price": fill_price,
            "submitted_at": time.time(),
        }

        if side == "buy" and qty >= FRAUD_REVIEW_QTY_THRESHOLD:
            order["reason"] = "flagged for suspected fraud: buy order size at or above review threshold"
            state["orders"].append(order)
            save_state(state)
            return order

        _execute_fill(state, order)
        state["orders"].append(order)
        save_state(state)
        return order


def confirm_order(order_id):
    with _lock:
        state = load_state()
        for o in state["orders"]:
            if o["id"] == order_id and o["status"] == "pending_confirmation":
                _execute_fill(state, o)
                save_state(state)
                return o
        return {"error": "no pending order with that id"}


def cancel_order(order_id):
    with _lock:
        state = load_state()
        for o in state["orders"]:
            if o["id"] == order_id and o["status"] not in ("filled", "rejected"):
                o["status"] = "cancelled"
                save_state(state)
                return o
        return {"error": "order not found or already settled"}


def get_portfolio_history():
    with _lock:
        state = load_state()
        return state["equity_history"]
