from .orderbookmanager import *
from binance.client import Client
import time
from binance import ThreadedWebsocketManager
import threading
import asyncio

class SpotOrderbooks(Orderbooks):
    def __init__(self, symbol, depth, client):
        super().__init__(symbol, depth)
        # self.get_snapshot(client, depth)
        self.client = client
        self.u = 0
        self.initialed = False
        self.in_snapshot_process = False
        self.first_socket_done = False

    def _get_snapshot(self, client, depth):
        self.in_snapshot_process = True
        orderbooks = client.get_order_book(symbol=self.symbol, limit=depth)
        self.lastUpdateId = orderbooks['lastUpdateId']
        t_ = int(time.time())
        for ask in orderbooks['asks'][:5]:
            self.create_orderbook(t_, float(ask[0]), float(ask[1]), ASK)
        for bid in orderbooks['bids'][:5]:
            self.create_orderbook(t_, float(bid[0]), float(bid[1]), BID)
        self.initialed = True
        self.in_snapshot_process = False


    def get_snapshot(self, client, depth):
        if self.in_snapshot_process:
            return
        thrd = threading.Thread(target=self._get_snapshot, args=(client, depth))
        thrd.start()

    def callback(self, msg):
        if not self.initialed:
            self.get_snapshot(self.client, self.depth)
            return
        event_time = msg['E']
        u = msg['u']
        U = msg['U']
        if not self.first_socket_done:
            if U > self.lastUpdateId or u < self.lastUpdateId:
                print(self.symbol + ': Start data is not valid')
                return
            else:
                print(self.symbol + ': Started with valid data')
                self.first_socket_done = True
        else:
            if U != self.u + 1:
                print(self.symbol + ': Data is not valid')
        for ask in msg['a']:
            self.create_orderbook(event_time, float(ask[0]), float(ask[1]), ASK)
        for bid in msg['b']:
            self.create_orderbook(event_time, float(bid[0]), float(bid[1]), BID)
        self.u = msg['u']


class SpotOrderbookManager(BaseOrderbookManager):
    def __init__(self, key, secret, symbols, depth=5):
        if len(symbols) >30:
            print('Too many symbols, it might not work correctly')
        self.symbols = list(map(lambda x: x.replace('-', ''), symbols))
        self.depth = depth
        self.key = key
        self.secret = secret
        self.orderbooks = {}
        self.client = Client(key, secret)

    def _init_orderbooks(self):
        for symbol in self.symbols:
            self.orderbooks[symbol] = SpotOrderbooks(symbol, self.depth, self.client)

    def start_socket(self):
        self.twm = ThreadedWebsocketManager(self.key, self.secret)
        self.twm.start()
        streams = [f'{symbol.lower()}@depth@100ms' for symbol in self.symbols]
        self.twm.start_multiplex_socket(callback=self.callback, streams=streams)
        # self.twm.join()

    def callback(self, msg):
        msg = msg['data']
        if msg['e'] != 'depthUpdate':
            return
        symbol = msg['s']
        orderbooks = self.orderbooks[symbol]
        orderbooks.callback(msg)

    def get(self, symbol) -> SpotOrderbooks:
        return self.orderbooks[symbol]

    def _start(self):
        self._init_orderbooks()
        self.start_socket()

    def start(self):
        thread = threading.Thread(target=self._start)
        thread.start()
        thread.join()

    def stop(self):
        self.twm.stop()



class FuturesOrderbooks(Orderbooks):
    def __init__(self, symbol, depth, client):
        super().__init__(symbol, depth)
        self.client = client
        self.u = 0
        self.initialed = False
        self.in_snapshot_process = False
        self.first_socket_done = False

    def _get_snapshot(self, client, depth):
        self.in_snapshot_process = True
        orderbooks = client.futures_order_book(symbol=self.symbol)
        self.lastUpdateId = orderbooks['lastUpdateId']
        t_ = int(time.time())
        for ask in orderbooks['asks'][:5]:
            self.create_orderbook(t_, float(ask[0]), float(ask[1]), ASK)
        for bid in orderbooks['bids'][:5]:
            self.create_orderbook(t_, float(bid[0]), float(bid[1]), BID)
        self.initialed = True
        self.in_snapshot_process = False

    def get_snapshot(self, client, depth):
        if self.in_snapshot_process:
            return
        thrd = threading.Thread(target=self._get_snapshot, args=(client, depth))
        thrd.start()

    def callback(self, msg):
        if not self.initialed:
            self.get_snapshot(self.client, self.depth)
            return
        event_time = msg['E']
        u = msg['u']
        U = msg['U']
        pu = msg['pu']
        if not self.first_socket_done:
            if U > self.lastUpdateId or u < self.lastUpdateId:
                print(self.symbol + ': Start data is not valid')
                return
            else:
                print(self.symbol + ': Started with valid data')
                self.first_socket_done = True
        else:
            if pu != self.u:
                print(self.symbol + ': Data is not valid')
        for ask in msg['a']:
            self.create_orderbook(event_time, float(ask[0]), float(ask[1]), ASK)
        for bid in msg['b']:
            self.create_orderbook(event_time, float(bid[0]), float(bid[1]), BID)
        self.u = u

class FuturesOrderbookManager(BaseOrderbookManager):
    def __init__(self, symbols, depth=5):
        if len(symbols) >30:
            print('Too many symbols, it might not work correctly')
        self.symbols = list(map(lambda x: x.replace('-', ''), symbols))
        self.depth = depth
        self.client = Client()

    def _init_orderbooks(self):
        self.orderbooks = {}
        for symbol in self.symbols:
            self.orderbooks[symbol] = FuturesOrderbooks(symbol, self.depth, self.client)

    def start_socket(self):
        self.twm = ThreadedWebsocketManager()
        self.twm.start()
        streams = [f'{symbol.lower()}@depth@100ms' for symbol in self.symbols]
        self.twm.start_futures_multiplex_socket(callback=self.callback, streams=streams)
        # self.twm.join()

    def callback(self, msg):
        msg = msg['data']
        if msg['e'] != 'depthUpdate':
            return
        symbol = msg['s']
        orderbooks = self.orderbooks[symbol]
        orderbooks.callback(msg)

    def get(self, symbol) -> FuturesOrderbooks:
        return self.orderbooks[symbol]

    def _start(self):
        self._init_orderbooks()
        self.start_socket()

    def start(self):
        thread = threading.Thread(target=self._start)
        thread.start()
        thread.join()

    def stop(self):
        self.twm.stop()