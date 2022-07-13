from ...orderbookmanager import *
from ...models import *
import time
from binance import ThreadedWebsocketManager
import threading
import asyncio
# from .symbol_translator import symboltranslator
import requests
import json
import hmac
import hashlib
from urllib.parse import urlencode
import random


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

    def __init__(self, exchange, paper, credentials={}) -> None:
        super().__init__()
        self.exchange = exchange
        self.paper = paper
        self.api_key = None
        self.api_secret = None
        self.position = None
        self.commision = 0.001
        if not paper:
            self.api_key = credentials['api_key']
            self.api_secret = credentials['api_secret']
        else:
            self.init_paper_mode()

    def get_listenkey(self):
        url = self.BASEL_URL + '/api/v3/userDataStream'
        headers = {'X-MBX-APIKEY': self.api_key}
        response = requests.post(url, headers=headers)
        return response.json()['listenKey']

    def calc_entry_commission(self, price, qty):
        # TODO: entry commision is decreased from the qty not the usdt
        return price * qty * 0.001

    def calc_exit_commission(self, price, qty):
        return price * qty * 0.001

    def keep_listenkey(self, listenkey):
        url = self.BASEL_URL + '/api/v3/userDataStream'
        headers = {'X-MBX-APIKEY': self.api_key}
        data = {'listenKey': listenkey}
        requests.put(url, headers=headers, data=data)

    def account_data_callback(self, msg):
        if msg['e'] != 'ACCOUNT_UPDATE':
            pass
        elif msg['e'] == 'ORDER_TRADE_UPDATE':
            self._update_order(msg)

    def _update_order(self, msg):
        """{
            "e":"ORDER_TRADE_UPDATE",     // Event Type
            "E":1568879465651,            // Event Time
            "T":1568879465650,            // Transaction Time
            "o":{
                "s":"BTCUSDT",              // Symbol
                "c":"TEST",                 // Client Order Id
                // special client order id:
                // starts with "autoclose-": liquidation order
                // "adl_autoclose": ADL auto close order
                // "settlement_autoclose-": settlement order for delisting or delivery
                "S":"SELL",                 // Side
                "o":"TRAILING_STOP_MARKET", // Order Type
                "f":"GTC",                  // Time in Force
                "q":"0.001",                // Original Quantity
                "p":"0",                    // Original Price
                "ap":"0",                   // Average Price
                "sp":"7103.04",             // Stop Price. Please ignore with TRAILING_STOP_MARKET order
                "x":"NEW",                  // Execution Type
                "X":"NEW",                  // Order Status
                "i":8886774,                // Order Id
                "l":"0",                    // Order Last Filled Quantity
                "z":"0",                    // Order Filled Accumulated Quantity
                "L":"0",                    // Last Filled Price
                "N":"USDT",             // Commission Asset, will not push if no commission
                "n":"0",                // Commission, will not push if no commission
                "T":1568879465650,          // Order Trade Time
                "t":0,                      // Trade Id
                "b":"0",                    // Bids Notional
                "a":"9.91",                 // Ask Notional
                "m":false,                  // Is this trade the maker side?
                "R":false,                  // Is this reduce only
                "wt":"CONTRACT_PRICE",      // Stop Price Working Type
                "ot":"TRAILING_STOP_MARKET",    // Original Order Type
                "ps":"LONG",                        // Position Side
                "cp":false,                     // If Close-All, pushed with conditional order
                "AP":"7476.89",             // Activation Price, only puhed with TRAILING_STOP_MARKET order
                "cr":"5.0",                 // Callback Rate, only puhed with TRAILING_STOP_MARKET order
                "pP": false,              // ignore
                "si": 0,                  // ignore
                "ss": 0,                  // ignore
                "rp":"0"                            // Realized Profit of the trade
            }
            }
            """
        # TODO: accquire lock
        updatetime = msg['E']
        order_update = msg['o']
        order = self.orders[order_update['i']]
        order.updatetime = updatetime
        order.status = order_update['X']
        order.avg_price = float(order_update['ap'])
        order.executed_quantity = float(order_update['z'])

    def buy_wallet(self, symbol, price, qty):
        return self._send_order(symbol, 'BUY', qty, price)

    def sell_wallet(self, symbol, price, qty):
        return self._send_order(symbol, 'SELL', qty, price)

    def _send_order(self, symbol, side, qty, price=None):
        url = self.BASEL_URL + '/fapi/v1/order'
        headers = {'X-MBX-APIKEY': self.api_key}
        params = self._create_order_data(
            symbol=symbol, side=side, qty=qty, price=price)
        response = requests.post(url, headers=headers, params=params).json()
        # TODO: manage errors
        self._add_order(response)
        return response['orderId']

    def _add_order(self, order):
        """{'orderId': 3067594093,
        'symbol': 'BTCUSDT', 
        'status': 'FILLED', 
        'clientOrderId': '465684561', 
        'price': '0', 
        'avgPrice': '19742.40000', 
        'origQty': '0.050', 
        'executedQty': '0.050', 
        'cumQty': '0.050', 
        'cumQuote': '987.12000', 
        'timeInForce': 'GTC', 
        'type': 'MARKET', 
        'reduceOnly': False, 
        'closePosition': False, 
        'side': 'SELL', 
        'positionSide': 'BOTH', 
        'stopPrice': '0', 
        'workingType': 'CONTRACT_PRICE', 
        'priceProtect': False, 
        'origType': 'MARKET', 
        'updateTime': 1657612049222}"""
        orderId = order['orderId']
        order_ = Order(
            id=orderId,
            symbol=order['symbol'],
            side=order['side'],
            status=order['status'],
            executed_quantity=order['executedQty'],
            price=order['price'],
            quantity=order['origQty'],
            avg_price=order['avgPrice'],
            updatetime=order['updateTime'],
        )
        self.orders[orderId] = order_

    def _get_new_order_id(self):
        while (id := str(random.randint(100000, 1000000))) in self.orders:
            pass
        return id

    def _create_order_data(self, **kwargs):
        price = kwargs.get('price', None)
        qty = kwargs.get('qty')
        symbol = kwargs.get('symbol')
        side = kwargs.get('side')
        newClientOrderId = self._get_new_order_id()
        data = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': qty,
            'newClientOrderId': newClientOrderId,
            'newOrderRespType': 'RESULT',
            'timestamp': str(int(time.time() * 1000))
        }
        if price is not None:
            data['price'] = price
            data['type'] = 'LIMIT'
        data['signature'] = self._sign_message(data)
        return data

    @staticmethod
    def _sign_message(data, api_secret=None):
        query_string = urlencode(data)
        signature = hmac.new(api_secret.encode(
            'utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature

    def _get_request_kwargs(self, method, signed: bool, force_params: bool = False, **kwargs):

        kwargs['timeout'] = self.REQUEST_TIMEOUT

        data = kwargs.get('data', None)
        if data and isinstance(data, dict):
            kwargs['data'] = data

            # find any requests params passed and apply them
            if 'requests_params' in kwargs['data']:
                # merge requests params into kwargs
                kwargs.update(kwargs['data']['requests_params'])
                del(kwargs['data']['requests_params'])

        if signed:
            # generate signature
            kwargs['data']['timestamp'] = int(
                time.time() * 1000 + self.timestamp_offset)
            kwargs['data']['signature'] = self._generate_signature(
                kwargs['data'])

        # sort get and post params to match signature order
        if data:
            # sort post params and remove any arguments with values of None
            kwargs['data'] = self._order_params(kwargs['data'])
            # Remove any arguments with values of None.
            null_args = [i for i, (key, value) in enumerate(
                kwargs['data']) if value is None]
            for i in reversed(null_args):
                del kwargs['data'][i]

        # if get request assign data array to params value for requests lib
        if data and (method == 'get' or force_params):
            kwargs['params'] = '&'.join('%s=%s' % (
                data[0], data[1]) for data in kwargs['data'])
            del(kwargs['data'])

        return kwargs
