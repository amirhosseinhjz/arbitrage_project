from ...orderbookmanager import *
import time
import threading
import asyncio
import requests
import base64
import hmac
import hashlib
import json
import random


class PerpOrderbooks(Orderbooks):
    def __init__(self, symbol, depth):
        super().__init__(symbol, depth)
        # self.u = 0
        # self.initialed = False
        # self.in_snapshot_process = False
        # self.first_socket_done = False
        # self.tries = 0

    def callback(self, msg):
        self.reset_orderbooks()
        event_time = msg['timestamp']  # //1000000
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


class PerpOrderbookManager(BaseOrderbookManager):
    def __init__(self, symbols, depth=5):
        self.symbols = symbols
        self.depth = depth
        self.orderbooks = {}

    def _init_orderbooks(self):
        for symbol in self.symbols:
            self.orderbooks[symbol] = PerpOrderbooks(
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

    def __call__(self, symbol) -> PerpOrderbooks:
        return self.orderbooks[symbol]




class PerpExchange(Exchange):
    API_URL = 'https://api-futures.kucoin.com'

    def __init__(self, pairs, private=False, credentials={}, testnet=False) -> None:
        super().__init__('binance', 'perp', pairs, private, credentials, testnet)
        self.BASEL_URL = self.TESTNET_API_URL if testnet else self.API_URL
        self.api_key = None
        self.api_secret = None
        self.api_passphrase = None
        self.commision = 0.0002
        if private:
            self.api_key = credentials['api_key']
            self.api_secret = credentials['api_secret']
            self.api_passphrase = credentials['api_passphrase']
        else:
            self.init_paper_mode()

    def get_orderbook_sbscription_message(self, symbols):
        topic = '/contractMarket/level2Depth50:' + ','.join(symbols)
        msg = {
            'type': 'subscribe',
            'topic': topic,
            'response': True,
            'id': str(int(time.time() * 1000)),
            'privateChannel': self.private
        }
        return json.dumps(msg)

    def socket_callback(self, msg):
        # print(msg)
        if not 'subject' in msg:
            return
        if msg['subject'] == 'level2':
            self.call_symbol_orderbooks(msg)

    def account_data_callback(self, msg):
        print(msg)
        pass

    def call_symbol_orderbooks(self, msg):
        if msg['subject'] != 'level2':
            return
        symbol = msg['topic'].split(':')[1]
        msg = msg['data']
        orderbooks = self.orderbooks[symbol]
        orderbooks.callback(msg)

    def start_socket(self):
        messages = [self.get_orderbook_sbscription_message(self.symbols)]
        kwargs = {
            'exchange': 'kucoin',
            'type': 'perp',
            'messages': messages,
            'callback': self.socket_callback,
            'token': None,
            'connectId': None,
        }
        if self.private:
            self.connectId = random.randint(10000, 1000000)
            kwargs['connectId'] = self.connectId
            kwargs['token'] = self.get_socket_token()
        socket = WebsocketManager.create(**kwargs)
        socket.start(multithread=False)

    def _start(self):
        print('Starting binance perp exchange')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._init_orderbooks(PerpOrderbooks)
        self.start_socket()

    def start(self):
        import nest_asyncio
        nest_asyncio.apply()
        self.thread = threading.Thread(target=self._start)
        self.thread.start()
        return self.thread

    def stop(self):
        pass

    # Manage orders:
    def _update_order(self, msg):
        pass

    def buy_wallet(self, symbol, price, qty):
        return self._send_order(symbol, 'BUY', qty, price)

    def sell_wallet(self, symbol, price, qty):
        return self._send_order(symbol, 'SELL', qty, price)

    def _send_order(self, symbol, side, qty, price=None):
        pass

    def cancel_order(self, order_id, symbol=None):
        pass

    def _add_order(self, order):
        pass



    def get_socket_token(self):
        headers = self.get_headers(
            self.api_key, self.api_secret, self.api_passphrase, 'POST', '/api/v1/bullet-private')
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