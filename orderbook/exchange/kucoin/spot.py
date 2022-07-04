from ...orderbookmanager import *
import time
import threading
import asyncio
# from .symbol_translator import symboltranslator
import requests
import base64
import hmac
import hashlib


class SpotOrderbooks(Orderbooks):
    # ORDERBOOK_URL = 'https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol='

    def __init__(self, symbol, depth):
        super().__init__(symbol, depth)
        # self.u = 0
        # self.initialed = False
        # self.in_snapshot_process = False
        # self.first_socket_done = False
        # self.tries = 0

    def callback(self, msg):
        self.reset_orderbooks()
        event_time = msg['timestamp']#//1000000
        # print('k', len(str(event_time)))
        for ask in msg['asks']:
            self.create_orderbook(
                event_time, float(ask[0]), float(ask[1]), ASK)
        for bid in msg['bids']:
            self.create_orderbook(
                event_time, float(bid[0]), float(bid[1]), BID)

    # def _get_snapshot(self, depth):
    #     self.tries += 1
    #     orderbooks = requests.get(
    #         self.ORDERBOOK_URL+self.symbol,
    #     ).json()['data']
    #     self.lastUpdateId = orderbooks['lastUpdateId']
    #     t_ = orderbooks['time']//1000
    #     for ask in orderbooks['asks'][:5]:
    #         self.create_orderbook(t_, float(ask[0]), float(ask[1]), ASK)
    #     for bid in orderbooks['bids'][:5]:
    #         self.create_orderbook(t_, float(bid[0]), float(bid[1]), BID)
    #     self.initialed = True
    #     self.in_snapshot_process = False

    # def get_snapshot(self, depth):
    #     if self.in_snapshot_process:
    #         return
    #     self.in_snapshot_process = True
    #     thrd = threading.Thread(
    #         target=self._get_snapshot, args=(depth,))
    #     thrd.start()


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
        if msg['subject'] != 'level2':
            return
        symbol = msg['topic'].split(':')[1]
        msg = msg['data']
        orderbooks = self.orderbooks[symbol]
        orderbooks.callback(msg)

    def __call__(self, symbol) -> SpotOrderbooks:
        return self.orderbooks[symbol]


class SpotAccount(AccountManager):
    BASEL_URL = 'https://api.kucoin.com'

    def __init__(self, api_key, api_secret, api_passphrase) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase

    def get_socket_token(self):
        headers = self.get_headers(self.api_key, self.api_secret, self.api_passphrase, 'POST', '/api/v1/bullet-private')
        return requests.post(
            self.BASEL_URL+'/api/v1/bullet-private',
            headers=headers,
        ).json()['data']['token']

    @staticmethod
    def get_headers(api_key, api_secret, api_passphrase, method, endpoint):
        now = int(time.time() * 1000)
        str_to_sign = str(now) + method + endpoint
        signature = base64.b64encode(hmac.new(
            api_secret.encode(), str_to_sign.encode(), hashlib.sha256).digest()).decode()
        passphrase = base64.b64encode(hmac.new(api_secret.encode(
        ), api_passphrase.encode(), hashlib.sha256).digest()).decode()
        return {'KC-API-KEY': api_key,
                'KC-API-KEY-VERSION': '2',
                'KC-API-PASSPHRASE': passphrase,
                'KC-API-SIGN': signature,
                'KC-API-TIMESTAMP': str(now)
                }

    # def keep_listenkey(self, listenkey):
    #     url = self.BASEL_URL + '/api/v3/userDataStream'
    #     headers = {'X-MBX-APIKEY': self.api_key}
    #     data = {'listenKey': listenkey}
    #     requests.put(url, headers=headers, data=data)

    # def account_data_callback(self, msg):
    #     if msg['e'] != 'ACCOUNT_UPDATE':
    #         return
    #     pass
