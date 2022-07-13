from ...orderbookmanager import *
import time
import threading
import asyncio
import requests
import json
import hmac
import hashlib
from urllib.parse import urlencode
import random
from ...socketmanager import WebsocketManager, Socket


class PerpOrderbooks(Orderbooks):
    ORDERBOOK_URL = 'https://fapi.binance.com/fapi/v1/depth'

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
        threading.Thread(
            target=self._get_snapshot, args=(depth,)).start()

    def callback(self, msg):
        if not self.initialed:
            self.get_snapshot(self.depth)
            return
        event_time = msg['E']
        u = msg['u']
        U = msg['U']
        pu = msg['pu']
        if not self.first_socket_done:
            if U > self.lastUpdateId or u < self.lastUpdateId:
                print(self.symbol +
                      ': Start data is not valid for time: ' + str(self.tries))
                self.get_snapshot(self.depth)
                return
            else:
                print(self.symbol + ': Started with valid data')
                self.first_socket_done = True
        else:
            if pu != self.u:
                print(self.symbol + ': Data is not valid')
        for ask in msg['a']:
            self.create_orderbook(
                event_time, float(ask[0]), float(ask[1]), ASK)
        for bid in msg['b']:
            self.create_orderbook(
                event_time, float(bid[0]), float(bid[1]), BID)
        self.u = u

class PerpExchange(Exchange):
    API_URL = 'https://fapi.binance.com'
    TESTNET_API_URL = 'https://testnet.binancefuture.com'

    def __init__(self, pairs, private=False, credentials={}, testnet=False) -> None:
        super().__init__('binance', 'perp', pairs, private, credentials, testnet)
        self.BASEL_URL = self.TESTNET_API_URL if testnet else self.API_URL
        self.api_key = None
        self.api_secret = None
        self.commision = 0.0002
        if private:
            self.api_key = credentials['api_key']
            self.api_secret = credentials['api_secret']
        else:
            self.init_paper_mode()

    def get_streams(self):
        return [f'{symbol.lower()}@depth@100ms' for symbol in self.symbols]

    def get_listenkey(self):
        url = self.BASEL_URL + '/fapi/v1/listenKey'
        headers = {'X-MBX-APIKEY': self.api_key}
        response = requests.post(url, headers=headers)
        return response.json()['listenKey']

    def keep_listenkey(self, listenkey):
        url = self.BASEL_URL + '/fapi/v3/userDataStream'
        headers = {'X-MBX-APIKEY': self.api_key}
        data = {'listenKey': listenkey}
        requests.put(url, headers=headers, data=data)

    def socket_callback(self, msg):
        # TODO: manage errors from websocket
        # print(msg)
        if 'data' in msg:
            msg = msg['data']
            if msg['e'] == 'depthUpdate':
                self.call_symbol_orderbooks(msg)
                return
        self.account_data_callback(msg)

    def account_data_callback(self, msg):
        # print(msg)
        if msg['e'] == 'ACCOUNT_UPDATE':
            pass
        elif msg['e'] == 'ORDER_TRADE_UPDATE':
            self._update_order(msg)

    def call_symbol_orderbooks(self, msg):
        symbol = msg['s']
        orderbooks = self.orderbooks[symbol]
        orderbooks.callback(msg)

    def start_socket(self):
        """
        TODO: fix the problem and run both orderbook and user data in one socket
        """
        kwargs = {'exchange': 'binance',
                  'type': 'perp',
                  'streams': self.get_streams(),
                  'callback': self.socket_callback,
                  'testnet': self.testnet}
        if self.private:
            kwargs['listenkey'] = self.get_listenkey()
        socket = WebsocketManager.create(**kwargs)
        print('Started socket')
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
        print(msg)
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
        # print(symbol)
        params = self._create_order_data(
            symbol=symbol, side=side, qty=qty, price=price)
        response = requests.post(url, headers=headers, params=params).json()
        # print(response)
        # TODO: manage errors
        self._add_order(response)
        return response['orderId']

    def cancel_order(self, order_id, symbol=None):
        if symbol is None:
            symbol = self.orders[order_id].symbol
        url = self.BASEL_URL + '/fapi/v1/order'
        headers = {'X-MBX-APIKEY': self.api_key}
        params = {'symbol': symbol, 'orderId': order_id}
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._sign_message(params, self.api_secret)
        response = requests.delete(url, headers=headers, params=params).json()
        print(response)

    def _add_order(self, order):
        """"{'orderId': 3067594093,
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

    def _create_order_data(self, **kwargs):
        price = kwargs.get('price', None)
        qty = kwargs.get('qty')
        symbol = kwargs.get('symbol')
        side = kwargs.get('side')
        # newClientOrderId = self._get_new_order_id()
        data = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': qty,
            # 'timeInForce': 'GTC',
            # 'newClientOrderId': newClientOrderId,
            'newOrderRespType': 'RESULT',
            'timestamp': str(int(time.time() * 1000))
        }
        if price is not None:
            data['price'] = price
            data['type'] = 'LIMIT'
            data['timeInForce'] = 'GTC'
        data['signature'] = self._sign_message(data, self.api_secret)
        return data

    @staticmethod
    def _sign_message(data, api_secret=None):
        query_string = urlencode(data)
        signature = hmac.new(api_secret.encode(
            'utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature
