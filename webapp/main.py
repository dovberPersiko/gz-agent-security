from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import broker

app = FastAPI(title="GZ Mock Broker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


class OrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str
    order_type: str = "market"
    limit_price: float | None = None


@app.get("/api/account")
def api_get_account():
    return broker.get_account()


@app.get("/api/positions")
def api_list_positions():
    return broker.list_positions()


@app.get("/api/symbols")
def api_list_symbols():
    return broker.list_symbols()


@app.get("/api/quote/{symbol}")
def api_get_quote(symbol: str):
    return broker.get_quote(symbol)


@app.get("/api/orders")
def api_list_orders(status: str = "all"):
    return broker.list_orders(status)


@app.post("/api/orders")
def api_place_order(req: OrderRequest):
    result = broker.place_order(req.symbol, req.qty, req.side, req.order_type, req.limit_price)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/orders/{order_id}/cancel")
def api_cancel_order(order_id: str):
    result = broker.cancel_order(order_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/orders/{order_id}/confirm")
def api_confirm_order(order_id: str):
    result = broker.confirm_order(order_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/portfolio-history")
def api_get_portfolio_history():
    return broker.get_portfolio_history()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
