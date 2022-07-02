import asyncio
import websockets
import threading
import requests

class Socket:
    def __init__(self, url, callback, messages=[]):
        self.url = url
        self.callback = callback
        self.messages_on_start = messages

    async def start_socket(self):
        try:
            async with websockets.connect(self.url) as websocket:
                while True:
                    while self.messages:
                        await websocket.send(self.messages.pop(0))
                    message = await websocket.recv()
                    self.callback(message)
        except Exception as e:
            print(e)
            self.start()

    def _start(self):
        self.messages = self.messages_on_start.copy()
        asyncio.get_event_loop().run_until_complete(self.start_socket())

    def start(self):
        self.thread = threading.Thread(target=self._start)
        self.thread.start()

    def stop(self):
        self.thread.join()

class RestApiUrl:
    KUCOIN_SPOT_URL = 'https://api.kucoin.com'

class OrderbookWebsocketManager:
    BINANCE_SPOT_BASE_URL = 'wss://stream.binance.com:9443/stream?streams='
    BINANCE_PERP_BASE_URL = 'wss://fstream.binance.com/stream?streams='
    KUCOIN_SPOT_BASE_URL = 'wss://ws-api.kucoin.com/endpoint'
    # BITFINEX_BASE_URL = 'wss://api-pub.bitfinex.com/ws/'


    @classmethod
    def create(cls, exhange, streams, callback):
        base_url = getattr(cls, f'{exhange.upper()}_BASE_URL')
        url = base_url + ''.join(streams)
        return Socket(url, callback)

    @classmethod
    def binance_spot_url(cls, streams):
        return cls.BINANCE_SPOT_BASE_URL + '/'.join(streams)

    @classmethod
    def binance_perp_url(cls, streams):
        return cls.BINANCE_PERP_BASE_URL + '/'.join(streams)

    @classmethod
    def kucoin_spot_url(cls, streams):
        token = requests.post(RestApiUrl.KUCOIN_SPOT_URL + '/api/v1/bullet-public').json()['data']['token']
        return cls.KUCOIN_SPOT_BASE_URL + '/'.join(streams)

    