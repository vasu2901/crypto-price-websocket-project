# 💹 Crypto Price WebSocket Server

A FastAPI-based application that streams **live cryptocurrency prices** from **Binance** and broadcasts them to **connected WebSocket clients** in real time.

---

## 🚀 Features
- Connects to Binance WebSocket for BTC/USDT and ETH/USDT  
- Runs a local WebSocket server at `ws://localhost:8000/ws`  
- Sends live updates and an initial snapshot to all clients  
- REST API endpoint: `GET /price` for latest prices  
- Graceful client connection and disconnection handling  

---

## 🧩 Setup & Run Locally

1. **Clone the repo**
   ```bash
   git clone https://github.com/vasu2901/crypto-price-websocket-project.git
   cd crypto-price-websocket-project
   ```
2. **Install dependencies**

```bash
python -m venv .venv # Create a virtual environment

# Start the Virtual Environment

.\.venv\Scripts\activate # For Windows
source .\.venv\bin\activate # for MacOS/Linux

#Install the dependencies
pip install -r requirements.txt
```
3. **Run the Server**
```bash
python main.py
```
4. **Connect a client**

WebSocket endpoint → ws://localhost:8000/ws

REST API endpoint → http://localhost:8000/price

