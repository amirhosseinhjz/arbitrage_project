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
    def __init__(self, exchange_name, symbol, depth, *args):
        super().__init__(exchange_name, symbol, depth)

    def callback(self, msg, symbol):
        self.reset_orderbooks()
        event_time = msg['timestamp']  # //1000000
        for ask in msg['asks']:
            self.create_orderbook(
                event_time, float(ask[0]), self.contract_size_to_qty(symbol, float(ask[1])), ASK)
        for bid in msg['bids']:
            self.create_orderbook(
                event_time, float(bid[0]), self.contract_size_to_qty(symbol, float(bid[1])), BID)


class PerpExchange(Exchange):
    API_URL = 'https://api-futures.kucoin.com'
    TESTNET_API_URL = 'https://api-sandbox-futures.kucoin.com'
    ORDER_STATUS_MAP = {
        'open': 'NEW', 'filled': 'FILLED', "canceled": "CANCELED", "match": 'PARTIALLY_FILLED', 'done': 'FILLED'}

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
            'privateChannel': False,
        }
        return json.dumps(msg)

    def get_userdata_subscription_msg(self, symbols):
        t_ = str(int(time.time() * 1000))
        positions = [{
            'type': 'subscribe',
            'topic': f'/contract/position:{symbol}',
            'response': True,
            'id': t_,
            'privateChannel': True,
        } for symbol in symbols]
        tradeorders = [{
            'type': 'subscribe',
            'topic': f'/contractMarket/tradeOrders:{symbol}',
            'response': True,
            'id': t_,
            'privateChannel': True,
        } for symbol in symbols]
        margin = {
            'type': 'subscribe',
            'topic': f'/contractAccount/wallet',
            'response': True,
            'id': t_,
            'privateChannel': True,
        }
        return list(map(json.dumps, positions + tradeorders + [margin]))
        # return [json.dumps(margin)]

    def start_socket(self):
        messages = [self.get_orderbook_sbscription_message(
            self.symbols)]  # [self.get_socket_announcement()]#
        if self.private:
            messages += self.get_userdata_subscription_msg(self.symbols)
        kwargs = {
            'exchange': 'kucoin',
            'type': 'perp',
            'messages': messages,
            'callback': self.socket_callback,
            'token': None,
            'connectId': None,
        }
        if self.private:
            self.connectId = self.generate_connectid()
            kwargs['connectId'] = self.connectId
            kwargs['token'] = self.get_socket_token()
        self.socket = WebsocketManager.create(**kwargs)
        self.socket.start(multithread=False)

    @staticmethod
    def generate_connectid():
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        return ''.join([random.choice(chars) for _ in range(32)])

    def _start(self):
        print('Starting kucoin perp exchange')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._init_orderbooks(PerpOrderbooks)
        self._cash = self.get_account_balance()
        self.start_socket()

    def start(self):
        import nest_asyncio
        nest_asyncio.apply()
        self.thread = threading.Thread(target=self._start)
        self.thread.start()
        return self.thread

    def stop(self):
        pass

        """{'type': 'message', 'topic': '/contract/position:XBTUSDTM', 'userId': '62d248548820e40001851507', 
        'channelType': 'private', 'subject': 'position.change', 'data': {'realisedGrossPnl': 0.0, 'symbol': 'XBTUSDTM', 
        'crossMode': False, 'liquidationPrice': 41120.0, 'posLoss': 0.0, 'avgEntryPrice': 20612.0, 'unrealisedPnl': -0.01147, 
        'markPrice': 20623.47, 'posMargin': 20.6367344, 'autoDeposit': False, 'riskLimit': 500000, 'unrealisedCost': -20.612, 
        'posComm': 0.0247344, 'posMaint': 0.1277944, 'posCost': -20.612, 'riskLimitLevel': 1, 'maintMarginReq': 0.005, 'bankruptPrice': 41224.0, 
        'realisedCost': 0.0123672, 'markValue': -20.62347, 'posInit': 20.612, 'realisedPnl': -0.0123672, 'maintMargin': 20.6252644, 
        'realLeverage': 1.0005567818, 'changeReason': 'positionChange', 'currentCost': -20.612, 'settleCurrency': 'USDT', 'openingTimestamp': 1657969819833, 
        'currentQty': -1, 'delevPercentage': 0.0, 'currentComm': 0.0123672, 'realisedGrossCost': 0.0, 'isOpen': True, 'posCross': 0.0, 'currentTimestamp': 1657969819833, 
        'unrealisedRoePcnt': -0.0006, 'unrealisedPnlPcnt': -0.0006}}
        {'type': 'message', 'topic': '/contract/position:XBTUSDTM', 'userId': '62d248548820e40001851507', 'channelType': 'private', 'subject': 'position.change', 
        'data': {'unrealisedPnl': -0.00754, 'symbol': 'XBTUSDTM', 'markPrice': 20619.54, 'maintMargin': 20.6291944, 'realLeverage': 1.0, 
        'changeReason': 'markPriceChange', 'currentTimestamp': 1657969824322, 'settleCurrency': 'USDT', 'unrealisedRoePcnt': -0.0004, 
        'unrealisedPnlPcnt': -0.0004, 'delevPercentage': 0.0, 'markValue': -20.61954}}"""
    # Manage websocket data:

    def socket_callback(self, msg):
        if not 'subject' in msg:
            print(msg)
            return
        if msg['subject'] == 'level2':
            self.call_symbol_orderbooks(msg)
        else:
            self.account_data_callback(msg)

    def account_data_callback(self, msg):
        if msg['topic'].startswith('/contractMarket/tradeOrders'):
            self._update_order(msg)
        elif msg['topic'].startswith('/contract/position'):
            pass
        elif msg['topic'].startswith('/contractAccount/wallet'):
            self._update_wallet_asset(msg)

    def call_symbol_orderbooks(self, msg):
        if msg['subject'] != 'level2':
            # print(msg)
            return
        symbol = msg['topic'].split(':')[1]
        msg = msg['data']
        with self.orderbook_lock:
            orderbooks = self.orderbooks[symbol]
            orderbooks.callback(msg, symbol)

    def _update_order(self, msg):
        """{'type': 'message', 'topic': '/contractMarket/tradeOrders:XBTUSDTM', 
        'userId': '62d248548820e40001851507', 'channelType': 'private', 
        'subject': 'symbolOrderChange', 'data': {
            'symbol': 'XBTUSDTM', 'orderType': 'market', 
            'side': 'buy', 'canceledSize': '0', 
            'orderId': '62d2bb753a1315000183dfab', 
            'liquidity': 'taker', 'type': 'match', 
            'orderTime': 1657977717222572417, 'size': '1', 
            'filledSize': '1', 'matchPrice': '20784', 
            'matchSize': '1', 'tradeId': '62d2bb753c7feb35232b289d', 
            'remainSize': '0', 'clientOid': '177455', 'status': 'match',
            'ts': 1657977717248936858}}
        {'type': 'message', 'topic': '/contractMarket/tradeOrders:XBTUSDTM', 
        'userId': '62d248548820e40001851507', 'channelType': 'private', 
        'subject': 'symbolOrderChange', 'data': {
            'symbol': 'XBTUSDTM', 'orderType': 'market', 
            'side': 'buy', 'canceledSize': '0', 'orderId': '62d2bb753a1315000183dfab',
            'type': 'filled', 'orderTime': 1657977717222572417, 'size': '1',
            'filledSize': '1', 'price': '', 'remainSize': '0',
            'clientOid': '177455', 'status': 'done',
            'ts': 1657977717248936858}}"""
        """{'type': 'message', 'topic': '/contractMarket/tradeOrders:XBTUSDTM', 
        'userId': '62d248548820e40001851507', 'channelType': 'private', 
        'subject': 'symbolOrderChange', 'data': {'symbol': 'XBTUSDTM', 
        'side': 'sell', 'canceledSize': '0', 'orderId': '62d2be7b307462000182dc1b', 
        'liquidity': 'maker', 'type': 'open', 'orderTime': 1657978491751105984, 
        'size': '1', 'filledSize': '0', 'price': '20795', 'remainSize': '1', 
        'clientOid': '659609', 'status': 'open', 'ts': 1657978491789412819}}


        {'type': 'message', 'topic': '/contractMarket/tradeOrders:XBTUSDTM',
        'userId': '62d248548820e40001851507', 'channelType': 'private', 'subject':
        .'symbolOrderChange', 'data': {'symbol': 'XBTUSDTM', 'orderType': 'limit',
        'side': 'sell', 'canceledSize': '0', 'orderId': '62d2be7b307462000182dc1b',
        'liquidity': 'maker', 'type': 'match', 'orderTime': 1657978491751105984,
        'size': '1', 'filledSize': '1', 'price': '20795', 'matchPrice': '20795',
        'matchSize': '1', 'remainSize': '0', 'tradeId': '62d2bea33c7feb352331bf71',
        'clientOid': '659609', 'status': 'done', 'ts': 1657978531524327990
            }
        }

        {'type': 'message', 'topic': '/contractMarket/tradeOrders:XBTUSDTM', 
        'userId': '62d248548820e40001851507', 'channelType': 'private', '
        subject': 'symbolOrderChange', 'data': {'symbol': 'XBTUSDTM', 'orderType': 
        'limit', 'side': 'sell', 'canceledSize': '0', 'orderId': '62d2be7b307462000182dc1b', 
        'type': 'filled', 'orderTime': 1657978491751105984, 'size': '1', 'filledSize': '1', 
        'price': '20795', 'remainSize': '0', 'clientOid': '659609', 'status': 'done', 
        'ts': 1657978531524327990
            }
        }"""
        if not msg['topic'].startswith('/contractMarket/tradeOrders'):
            return
        # print(msg)
        msg = msg['data']
        orderId = msg['orderId']
        symbol = msg['symbol']
        status = msg['status']
        status = self.ORDER_STATUS_MAP.get(status, status)
        side = msg['side'].upper()
        price = msg.get('price', None)
        matchPrice = msg.get('matchPrice', None)
        price = price if price else matchPrice
        qty = self.contract_size_to_qty(symbol, float(msg['size']))
        updatetime = msg['ts']//10**9
        order = self.orders.get(orderId, None)
        if order is None:  # and status == 'NEW':
            self._add_order({'id': orderId, 'symbol': symbol,
                             'side': side, 'price': price, 'qty': qty, 'updateTime': updatetime})
            # TODO: handle order not found
            # print('update order not found:', orderId)
            return
        filledSize = float(msg['filledSize'])
        filledSize = self.contract_size_to_qty(symbol, filledSize)
        order.update(executed_quantity=filledSize, status=status,
                     avg_price=matchPrice, updatetime=updatetime)

    def _update_wallet_asset(self, msg):
        """{'id': '62d3fd18c46e7c0001d32194', 'type': 'message', 
        'topic': '/contractAccount/wallet', 'userId': '62d248548820e40001851507', 
        'channelType': 'private', 'subject': 'availableBalance.change', 'data': 
        {'currency': 'USDT', 'holdBalance': '21.4887556000', 'availableBalance': 
        '8.0657778050', 'timestamp': '1658060056357'}}"""
        if not msg['topic'].startswith('/contractAccount/wallet'):
            return
        msg = msg['data']
        currency = msg['currency']
        if currency != 'USDT':
            print(msg)
            return
        cash = msg.get('availableBalance', None)
        if cash:
            self._cash = float(cash)

    def buy_wallet(self, symbol, price, qty):
        return self._send_order(symbol, 'BUY', qty, price)

    def sell_wallet(self, symbol, price, qty):
        return self._send_order(symbol, 'SELL', qty, price)

    def get_account_balance(self, currency='USDT'):
        if not self.private:
            return 10000
        return self._get_account_overview(currency)['data']['availableBalance']

    def get_market_contract_list(self):
        endpoint = '/api/v1/contracts/active'
        url = self.BASEL_URL + endpoint
        response = requests.get(url).json()
        return response

    def _send_order(self, symbol, side, qty, price=None, leverage=1):
        id = self.generate_order_id()
        size = self.qty_to_contract_size(symbol, qty)
        params = {
            'clientOid': id,
            'symbol': symbol,
            'size': size,
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
        response_data = requests.post(url, headers=headers, data=json_params,
                                      timeout=self.REQUEST_TIMEOUT).json()
        try:
            return response_data['data']['orderId']
        except KeyError:
            print(response_data)
            raise Exception('Error creating order')

    def _get_account_overview(self, currency):
        endpoint = '/api/v1/account-overview?currency=' + currency
        headers = self._get_order_headers('GET', endpoint)
        url = self.BASEL_URL + endpoint
        response_data = requests.get(
            url, headers=headers, timeout=self.REQUEST_TIMEOUT)
        return response_data.json()

    def cancel_order(self, order_id, symbol=None):
        endpoint = '/api/v1/orders/' + str(order_id)
        headers = self._get_order_headers('DELETE', endpoint)
        url = self.BASEL_URL + endpoint
        response_data = requests.delete(url, headers=headers,
                                        timeout=self.REQUEST_TIMEOUT).json()
        print(response_data)
        # del self.orders[order_id]

    def _add_order(self, order):
        orderId = order['id']
        order_ = Order(
            id=orderId,
            symbol=order['symbol'],
            side=order['side'],
            status='NEW',
            price=order['price'],
            quantity=order['qty'],
            updatetime=order['updateTime'],
        )
        self.orders[orderId] = order_

    def get_socket_token(self):
        headers = self.get_headers(
            self.api_key, self.api_secret, self.api_passphrase, 'POST', '/api/v1/bullet-private')
        return requests.post(
            self.BASEL_URL+'/api/v1/bullet-private',
            headers=headers,
        ).json()['data']['token']

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

    def get_valid_qty(self, pair, qty):
        symbol = symboltranslator(self, *pair)
        contract_size = self.qty_to_contract_size(symbol, qty)
        contract_size = int(contract_size)
        qty = self.contract_size_to_qty(symbol, contract_size)
        if self.is_valid_qty(symbol, qty):
            return qty
        return 0