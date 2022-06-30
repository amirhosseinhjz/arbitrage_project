import asyncio
import websockets
import threading


class Socket:
    def __init__(self, url, callback):
        self.url = url
        self.callback = callback

    async def start_socket(self):
        async with websockets.connect(self.url) as websocket:
            while True:
                response = await websocket.recv()
                self.callback(response)

    def _start(self):
        asyncio.get_event_loop().run_until_complete(self.start_socket())

    def start(self):
        self.thread = threading.Thread(target=self._start)
        self.thread.start()

    def stop(self):
        self.thread.join()


class OrderbookWebsocketManager:
    BINANCE_BASE_URL = 'wss://stream.binance.com:9443/stream?streams='
    BITFINEX_BASE_URL = 'wss://api-pub.bitfinex.com/ws/'


    @classmethod
    def create(cls, exhange, streams, callback):
        base_url = getattr(cls, f'{exhange.upper()}_BASE_URL')
        url = base_url + ''.join(streams)
        return Socket(url, callback)