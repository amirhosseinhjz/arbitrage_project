from itsdangerous import json
from .orderbookmanager import *
from .exchange.kucoin import spot, perp
import time
import threading
import asyncio
from .symbol_translator import symboltranslator
import requests
from .socketmanager import WebsocketManager
import base64
import hmac
import hashlib
import json
import random


class SpotExchange(Exchange):
    def __init__(self, pairs, private, **credentials) -> None:
        super().__init__('kucoin', 'spot')
        self.symbols = self.translate_pairs(pairs)
        self.orderbookmanager = spot.SpotOrderbookManager(self.symbols)
        self.account = spot.SpotAccount(
            exchange=self, paper=not private, credentials=credentials)
        self.socket_token = None
        self._private = private
        if private:
            self.socket_token = self.account.get_socket_token()

    def get_orderbook_sbscription_message(self, symbols):
        topic = '/spotMarket/level2Depth50:' + ','.join(symbols)
        msg = {
            'type': 'subscribe',
            'topic': topic,
            'response': True,
            'id': str(int(time.time() * 1000)),
            'privateChannel': self._private
        }
        return json.dumps(msg)

    def start_socket(self):
        messages = [self.get_orderbook_sbscription_message(self.symbols)]
        if self._private:
            connectId = str(random.randint(1, 1000000))
        else:
            connectId = None
        socket = WebsocketManager.create(
            exchange='kucoin', type='spot', callback=self.socket_callback, messages=messages, token=self.socket_token, connectId=connectId)
        socket.start(multithread=False)

    def socket_callback(self, msg):
        if not 'subject' in msg:
            return
        if msg['subject'] == 'level2':
            self.orderbookmanager.call_symbol_orderbooks(msg)

    def _start(self):
        print('Starting kucoin spot exchange')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.orderbookmanager._init_orderbooks()
        self.start_socket()

    def start(self):
        import nest_asyncio
        nest_asyncio.apply()
        thread = threading.Thread(target=self._start)
        thread.start()
        # thread.join()

    def stop(self):
        self.twm.stop()


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


class PerpExchange(Exchange):
    API_URL = 'https://api-futures.kucoin.com'

    def __init__(self, pairs, private=False, credentials={}, testnet=False) -> None:
        super().__init__('kucoin', 'perp', pairs, private, credentials, testnet)
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
        with self.orderbook_lock:
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

    def _send_order(self, symbol, side, qty, price=None, leverage=1):
        id = self.generate_order_id()
        params = {
            'clientOid': id,
            'symbol': symbol,
            'size': qty,
            'side': side,
            'leverage': leverage,
            'type': 'market',
        }
        if price:
            params['price'] = price
            params['type'] = 'limit'
        json_params = json.dumps(params)
        endpoint = '/api/v1/orders'
        headers = self._get_order_headers('POST', endpoint + json_params)
        url = self.BASEL_URL + endpoint
        print(url)
        response_data = requests.post(url, headers=headers, data=json_params,
                                timeout=self.REQUEST_TIMEOUT).json()
        print(response_data)

    def cancel_order(self, order_id, symbol=None):
        endpoint = '/api/v1/orders/' + str(order_id)
        headers = self._get_order_headers('DELETE', endpoint)
        url = self.BASEL_URL + endpoint
        print(url)
        response_data = requests.delete(url, headers=headers,
                                timeout=self.REQUEST_TIMEOUT).json()
        print(response_data)

    def _add_order(self, order):
        pass

    def get_socket_token(self):
        headers = self.get_headers(
            self.api_key, self.api_secret, self.api_passphrase, 'POST', '/api/v1/bullet-private')
        return requests.post(
            self.BASEL_URL+'/api/v1/bullet-private',
            headers=headers,
        ).json()['data']['token']

    # def _sign_message(self, time_, method, endpoint):

    def _get_order_headers(self, method, endpoint):
        time_ = int(time.time()) * 1000
        str_to_sign = str(time_) + method + endpoint
        sign = base64.b64encode(
                hmac.new(self.api_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
        passphrase = base64.b64encode(
                    hmac.new(self.api_secret.encode('utf-8'), self.api_passphrase.encode('utf-8'), hashlib.sha256).digest())
        headers = {
                    "KC-API-SIGN": sign,
                    "KC-API-TIMESTAMP": str(time_),
                    "KC-API-KEY": self.api_key,
                    "KC-API-PASSPHRASE": passphrase,
                    "Content-Type": "application/json",
                    "KC-API-KEY-VERSION": "2"
                }
        return headers

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
