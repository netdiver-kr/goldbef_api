"""
Mock WebSocket Server for Testing
실제 API 키 없이 시스템을 테스트할 수 있는 더미 서버

사용법:
1. 터미널 1에서 실행: python test_mock_server.py
2. 터미널 2에서 메인 앱 실행: uvicorn app.main:app --reload
"""

import asyncio
import json
import random
from datetime import datetime
from websockets.server import serve
from websockets.exceptions import ConnectionClosed


class MockPriceServer:
    """Mock price data generator"""

    def __init__(self):
        self.base_prices = {
            'XAUUSD': 2050.0,   # Gold
            'XAGUSD': 24.5,     # Silver
            'USDKRW': 1320.0    # USD/KRW
        }

    def generate_price(self, symbol: str) -> dict:
        """Generate realistic price data"""
        base_price = self.base_prices.get(symbol, 100.0)

        # Random price movement
        change = random.uniform(-0.5, 0.5)
        price = base_price + change

        # Update base price for next iteration
        self.base_prices[symbol] = price

        # Generate bid/ask
        spread = price * 0.0002  # 0.02% spread
        bid = price - spread / 2
        ask = price + spread / 2

        return {
            's': symbol,
            'p': round(price, 2),
            'b': round(bid, 2),
            'a': round(ask, 2),
            'v': random.randint(1000, 50000),
            't': int(datetime.utcnow().timestamp() * 1000)
        }


async def handle_client(websocket, path):
    """Handle WebSocket client connection"""
    print(f"Client connected: {websocket.remote_address}")

    price_server = MockPriceServer()
    symbols = ['XAUUSD', 'XAGUSD', 'USDKRW']

    try:
        # Wait for subscribe message
        subscribe_msg = await websocket.recv()
        print(f"Received: {subscribe_msg}")

        # Send confirmation
        await websocket.send(json.dumps({
            "status": "subscribed",
            "symbols": symbols
        }))

        # Send price updates every second
        while True:
            for symbol in symbols:
                price_data = price_server.generate_price(symbol)
                await websocket.send(json.dumps(price_data))

            await asyncio.sleep(1)

    except ConnectionClosed:
        print(f"Client disconnected: {websocket.remote_address}")
    except Exception as e:
        print(f"Error: {e}")


async def main():
    """Start mock WebSocket server"""
    port = 9000
    print("=" * 50)
    print("Mock WebSocket Price Server")
    print("=" * 50)
    print(f"Listening on: ws://localhost:{port}")
    print("Generating mock price data for:")
    print("  - XAUUSD (Gold)")
    print("  - XAGUSD (Silver)")
    print("  - USDKRW (USD/KRW)")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 50)
    print()

    async with serve(handle_client, "localhost", port):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
