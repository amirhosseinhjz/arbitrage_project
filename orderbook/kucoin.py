from .orderbookmanager import *
from kucoin.client import Client
from kucoin_futures.client import Market
from kucoin.asyncio import KucoinSocketManager
from kucoin_futures.client import WsToken
from kucoin_futures.ws_client import KucoinFuturesWsClient
import time
import asyncio
import threading
import nest_asyncio
from .symbol_translator import symboltranslator


class SpotOrderbooks(Orderbooks):
    def __init__(self, symbol, depth, client):
        super().__init__(symbol, depth)
        self.get_snapshot(client, depth)

    def get_snapshot(self, client, depth):
        orderbooks = client.get_order_book(symbol=self.symbol)
        t_ = orderbooks['time']
        for ask in orderbooks['asks'][:5]:
            self.create_orderbook(t_, float(ask[0]), float(ask[1]), ASK)
        for bid in orderbooks['bids'][:5]:
            self.create_orderbook(t_, float(bid[0]), float(bid[1]), BID)

    def callback(self, msg):
        self.reset_orderbooks()
        event_time = msg['timestamp']//1000
        for ask in msg['asks']:
            self.create_orderbook(event_time, float(ask[0]), float(ask[1]), ASK)
        for bid in msg['bids']:
            self.create_orderbook(event_time, float(bid[0]), float(bid[1]), BID)

class SpotOrderbookManager(BaseOrderbookManager):
    def __init__(self, api_key, api_secret, 
                            api_passphrase ,pairs, depth=5):
        if len(pairs) > 30:
            print('Too many symbols, it might not work correctly')
        symbols = []
        for pair in pairs:
            symbols.append(symboltranslator('kucoin', pair[0], pair[1], 'spot'))
        self.symbols = symbols
        self.depth = depth
        self.client = Client(api_key, api_secret, api_passphrase)

    def _init_orderbooks(self):
        self.orderbooks = {}
        for symbol in self.symbols:
            self.orderbooks[symbol] = SpotOrderbooks(symbol, self.depth, self.client)

    async def _start_socket(self):
        ksm = await KucoinSocketManager.create(self.loop, self.client, self.callback)

        await ksm.subscribe('/spotMarket/level2Depth50:'+ ','.join(self.symbols))

        while True:
            # print("sleeping to keep loop open")
            await asyncio.sleep(20, loop=self.loop)

    async def callback(self, msg):
        if msg['subject'] != 'level2':
            return
        symbol = msg['topic'].split(':')[1]
        msg = msg['data']
        orderbooks = self.orderbooks[symbol]
        orderbooks.callback(msg)

    def get(self, symbol) -> SpotOrderbooks:
        return self.orderbooks[symbol]

    def _start(self):
        # nest_asyncio.apply()
        self._init_orderbooks()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._start_socket())

    def start(self):
        self.thread = threading.Thread(target=self._start)
        self.thread.start()
        # self.thread.join()

    def stop(self):
        self.loop.stop()
        self.thread.join()

class FuturesOrderbooks(Orderbooks):
    def __init__(self, symbol, depth, client):
        super().__init__(symbol, depth)
        self.get_snapshot(client, depth)

    def get_snapshot(self, client, depth):
        orderbooks = client.l2_order_book(symbol=self.symbol)
        t_ = orderbooks['ts'] // 1000000000 #ns to s
        for ask in orderbooks['asks'][:5]:
            self.create_orderbook(t_, float(ask[0]), float(ask[1]), ASK)
        for bid in orderbooks['bids'][:5]:
            self.create_orderbook(t_, float(bid[0]), float(bid[1]), BID)

    def callback(self, msg):
        self.reset_orderbooks()
        event_time = msg['ts']//1000000000 #ns to s
        for ask in msg['asks']:
            self.create_orderbook(event_time, float(ask[0]), float(ask[1]), ASK)
        for bid in msg['bids']:
            self.create_orderbook(event_time, float(bid[0]), float(bid[1]), BID)


class FuturesOrderbookManager(BaseOrderbookManager):
    def __init__(self, api_key, api_secret, 
                            api_passphrase ,pairs, depth=5):
        if len(pairs) > 30:
            print('Too many symbols, it might not work correctly')
        symbols = []
        for pair in pairs:
            symbols.append(symboltranslator('kucoin', pair[0], pair[1], 'perp'))
        self.symbols = symbols
        self.depth = depth
        self.client = Market(url='https://api-futures.kucoin.com')
        self.ws_client = WsToken(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='')

    def _init_orderbooks(self):
        self.orderbooks = {}
        for symbol in self.symbols:
            self.orderbooks[symbol] = FuturesOrderbooks(symbol, self.depth, self.client)

    async def _start_socket(self):
        ws_client = await KucoinFuturesWsClient.create(self.loop, self.ws_client, self.callback, private=False)
        await ws_client.subscribe('/contractMarket/level2Depth50:'+ ','.join(self.symbols))
        while True:
            # print("sleeping to keep loop open")
            await asyncio.sleep(20, loop=self.loop)

    async def callback(self, msg):
        if msg['subject'] != 'level2':
            return
        symbol = msg['topic'].split(':')[1]
        msg = msg['data']
        orderbooks = self.orderbooks[symbol]
        orderbooks.callback(msg)

    def get(self, symbol) -> FuturesOrderbooks:
        return self.orderbooks[symbol]

    def _start(self):
        self._init_orderbooks()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._start_socket())

    def start(self):
        self.thread = threading.Thread(target=self._start)
        self.thread.start()
        # self.thread.join()

    def stop(self):
        self.loop.stop()
        self.thread.join()