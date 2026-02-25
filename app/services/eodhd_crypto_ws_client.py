import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.services.base_ws_client import BaseWebSocketClient
from app.utils.logger import app_logger as logger


class EODHDCryptoWebSocketClient(BaseWebSocketClient):
    """
    EODHD Crypto WebSocket Client

    Connects to wss://ws.eodhistoricaldata.com/ws/crypto for cryptocurrency data.
    Separate from the forex endpoint which handles metals and currency pairs.
    """

    SYMBOL_MAPPING = {
        'btc_usd': 'BTC-USD',
    }

    @property
    def provider_name(self) -> str:
        return "eodhd_crypto"

    def get_websocket_url(self) -> str:
        return f"wss://ws.eodhistoricaldata.com/ws/crypto?api_token={self.api_key}"

    def get_subscribe_message(self) -> Dict[str, Any]:
        symbols = ','.join(self.SYMBOL_MAPPING.values())
        return {
            "action": "subscribe",
            "symbols": symbols
        }

    def parse_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
        try:
            logger.debug(f"[{self.provider_name}] Raw message: {raw_message[:200]}")

            data = json.loads(raw_message)

            # Log subscription status/messages
            if 'status' in data or 'message' in data or 'status_code' in data:
                logger.info(f"[{self.provider_name}] Status: {data}")
                return None

            symbol = data.get('s') or data.get('symbol')
            if not symbol:
                return None

            # Map symbol back to asset_type
            asset_type = None
            for asset, sym in self.SYMBOL_MAPPING.items():
                if sym == symbol:
                    asset_type = asset
                    break

            if not asset_type:
                logger.warning(f"[{self.provider_name}] Unknown symbol: {symbol}")
                return None

            # Extract price
            price = data.get('p') or data.get('price')
            if price is None:
                bid = data.get('b') or data.get('bid')
                ask = data.get('a') or data.get('ask')
                if ask is not None:
                    price = float(ask)
                elif bid is not None:
                    price = float(bid)
                else:
                    logger.debug(f"[{self.provider_name}] No price data in message: {data}")
                    return None

            # Parse timestamp
            timestamp = None
            if 't' in data or 'timestamp' in data:
                ts_ms = data.get('t') or data.get('timestamp')
                timestamp = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) if ts_ms else None

            return {
                'provider': 'eodhd',
                'asset_type': asset_type,
                'price': float(price),
                'bid': float(data.get('b') or data.get('bid')) if ('b' in data or 'bid' in data) else None,
                'ask': float(data.get('a') or data.get('ask')) if ('a' in data or 'ask' in data) else None,
                'volume': float(data.get('v') or data.get('volume')) if ('v' in data or 'volume' in data) else None,
                'timestamp': timestamp,
                'metadata': {
                    'symbol': symbol
                }
            }

        except json.JSONDecodeError as e:
            logger.error(f"[{self.provider_name}] Failed to decode JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"[{self.provider_name}] Error parsing message: {e}")
            logger.debug(f"[{self.provider_name}] Raw message: {raw_message}")
            return None
