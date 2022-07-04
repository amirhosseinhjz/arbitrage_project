from ...orderbookmanager import *
import time
from binance import ThreadedWebsocketManager
import threading
import asyncio
# from .symbol_translator import symboltranslator
import requests


class SpotOrderbooks(Orderbooks):
    ORDERBOOK_URL = 'https://api.binance.com/api/v3/depth'

    def __init__(self, symbol, depth):
        super().__init__(symbol, depth)
        self.u = 0
        self.initialed = False
        self.in_snapshot_process = False
        self.first_socket_done = False
        self.tries = 0

    def _get_snapshot(self, depth):
        self.tries += 1
        orderbooks = requests.get(
            self.ORDERBOOK_URL,
            params={'symbol': self.symbol, 'limit': depth}
        ).json()
        self.lastUpdateId = orderbooks['lastUpdateId']
        t_ = int(time.time())
        for ask in orderbooks['asks'][:5]:
            self.create_orderbook(t_, float(ask[0]), float(ask[1]), ASK)
        for bid in orderbooks['bids'][:5]:
            self.create_orderbook(t_, float(bid[0]), float(bid[1]), BID)
        self.initialed = True
        self.in_snapshot_process = False

    def get_snapshot(self, depth):
        if self.in_snapshot_process:
            return
        self.in_snapshot_process = True
        thrd = threading.Thread(
            target=self._get_snapshot, args=(depth,))
        thrd.start()

    def callback(self, msg):
        if not self.initialed:
            self.get_snapshot(self.depth)
            return
        event_time = msg['E']
        # print('b', len(str(event_time)))
        u = msg['u']
        U = msg['U']
        if not self.first_socket_done:
            if U > self.lastUpdateId or u < self.lastUpdateId:
                print(self.symbol +
                      ': Start data is not valid for time: ' + str(self.tries))
                self.initialed = True
                self.get_snapshot(self.depth)
                return
            else:
                print(self.symbol + ': Started with valid data')
                self.first_socket_done = True
        else:
            if U != self.u + 1:
                print(self.symbol + ': Data is not valid')
        for ask in msg['a']:
            self.create_orderbook(
                event_time, float(ask[0]), float(ask[1]), ASK)
        for bid in msg['b']:
            self.create_orderbook(
                event_time, float(bid[0]), float(bid[1]), BID)
        self.u = msg['u']


class SpotOrderbookManager(BaseOrderbookManager):
    def __init__(self, symbols, depth=5):
        self.symbols = symbols
        self.depth = depth
        self.orderbooks = {}

    def _init_orderbooks(self):
        for symbol in self.symbols:
            self.orderbooks[symbol] = SpotOrderbooks(
                symbol, self.depth)

    def callback(self, msg):
        self.call_symbol_orderbooks(msg)

    def call_symbol_orderbooks(self, msg):
        symbol = msg['s']
        orderbooks = self.orderbooks[symbol]
        orderbooks.callback(msg)

    def __call__(self, symbol) -> SpotOrderbooks:
        return self.orderbooks[symbol]


class SpotAccount(AccountManager):
    BASEL_URL = 'https://api.binance.com'

    def __init__(self, api_key, api_secret) -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    def get_listenkey(self):
        url = self.BASEL_URL + '/api/v3/userDataStream'
        headers = {'X-MBX-APIKEY': self.api_key}
        response = requests.post(url, headers=headers)
        return response.json()['listenKey']

    def keep_listenkey(self, listenkey):
        url = self.BASEL_URL + '/api/v3/userDataStream'
        headers = {'X-MBX-APIKEY': self.api_key}
        data = {'listenKey': listenkey}
        requests.put(url, headers=headers, data=data)

    def account_data_callback(self, msg):
        if msg['e'] != 'ACCOUNT_UPDATE':
            return
        pass
