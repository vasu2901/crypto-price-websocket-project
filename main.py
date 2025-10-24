import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Set, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK


BINANCE_STREAM_BASE = "wss://stream.binance.us:9443/stream?streams="
PAIRS = os.getenv("PAIRS", "btcusdt,ethusdt").split(",")
STREAMS = "/".join(f"{pair.lower()}@ticker" for pair in PAIRS)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crypto-stream")

app = FastAPI(title="Crypto Price WebSocket Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: Set[WebSocket] = set()
client_lock = asyncio.Lock()
price_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
latest_prices: Dict[str, Dict[str, Any]] = {}
stop_event = asyncio.Event()


def format_timestamp(ms: int) -> str:
    """Convert Binance millisecond timestamp to readable UTC date/time."""
    return datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


async def listen_to_binance():
    """Connect to Binance WebSocket and push messages into the queue."""
    url = BINANCE_STREAM_BASE + STREAMS
    backoff = 1
    max_backoff = 60

    while not stop_event.is_set():
        try:
            logger.info(f"Connecting to Binance: {url}")
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                logger.info("Connected to Binance")
                backoff = 1

                async for raw_message in ws:
                    if stop_event.is_set():
                        break

                    try:
                        message = json.loads(raw_message)
                        payload = message.get("data") or message
                        parsed = parse_binance_message(payload)
                        if parsed:
                            try:
                                price_queue.put_nowait(parsed)
                            except asyncio.QueueFull:
                                _ = price_queue.get_nowait()
                                price_queue.put_nowait(parsed)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON message from Binance")

        except (ConnectionClosedOK, ConnectionClosedError) as e:
            logger.warning(f"Binance connection closed: {e}")
        except Exception as e:
            logger.exception(f"Binance listener error: {e}")

        if not stop_event.is_set():
            logger.info(f"Reconnecting to Binance in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


def parse_binance_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and format relevant ticker data."""
    symbol = data.get("s")
    price = data.get("c")
    change_percent = data.get("P")
    timestamp = data.get("E")

    if not symbol or not price:
        return {}

    return {
        "symbol": symbol,
        "lastPrice": float(price),
        "priceChangePercent": float(change_percent) if change_percent else None,
        "eventTime": format_timestamp(timestamp) if timestamp else None,
    }


async def broadcast_prices():
    """Send price updates to all connected WebSocket clients."""
    while not stop_event.is_set():
        try:
            update = await price_queue.get()
            if not update:
                continue

            symbol = update.get("symbol")
            if symbol:
                latest_prices[symbol] = update

            message_text = json.dumps(update)
            async with client_lock:
                clients_snapshot = set(connected_clients)

            stale_clients = []
            for client in clients_snapshot:
                try:
                    await client.send_text(message_text)
                except Exception:
                    stale_clients.append(client)

            if stale_clients:
                async with client_lock:
                    for client in stale_clients:
                        connected_clients.discard(client)

        except Exception as e:
            logger.exception(f"Error broadcasting prices: {e}")
            await asyncio.sleep(0.5)


@app.websocket("/ws")
async def websocket_handler(websocket: WebSocket):
    """Handle WebSocket connections from clients."""
    await websocket.accept()
    logger.info(f"Client connected: {websocket.client}")
    async with client_lock:
        connected_clients.add(websocket)

    try:
        snapshot = {"type": "snapshot", "prices": latest_prices}
        await websocket.send_text(json.dumps(snapshot))

        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info(f"Client disconnected: {websocket.client}")
                break
            except Exception:
                await asyncio.sleep(0.1)
    finally:
        async with client_lock:
            connected_clients.discard(websocket)


@app.get("/price")
async def get_price(symbol: str = None):
    """Return the latest prices or a specific symbol."""
    if symbol:
        symbol = symbol.upper()
        if symbol in latest_prices:
            return JSONResponse({symbol: latest_prices[symbol]})
        return JSONResponse({"error": "Symbol not found"}, status_code=404)
    return JSONResponse(latest_prices)


@app.on_event("startup")
async def on_startup():
    logger.info("Starting background tasks...")
    app.state.listener_task = asyncio.create_task(listen_to_binance())
    app.state.broadcaster_task = asyncio.create_task(broadcast_prices())


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down...")
    stop_event.set()
    for task_name in ("listener_task", "broadcaster_task"):
        task = getattr(app.state, task_name, None)
        if task:
            task.cancel()

    async with client_lock:
        for ws in list(connected_clients):
            try:
                await ws.close()
            except Exception:
                pass
        connected_clients.clear()
    logger.info("Shutdown complete.")
