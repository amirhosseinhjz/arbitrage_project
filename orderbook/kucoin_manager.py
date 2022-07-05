from itsdangerous import json
from .orderbookmanager import *
from .exchange.kucoin import spot, perp
import time
import threading
import asyncio
from .symbol_translator import symboltranslator
import requests
from .socketmanager import WebsocketManager
import random

class SpotExchange(Exchange):
    def __init__(self, pairs, private, **credentials) -> None:
        super().__init__('kucoin', 'spot')
        self.symbols = self.translate_pairs(pairs)
        self.orderbookmanager = spot.SpotOrderbookManager(self.symbols)
        self.account = spot.SpotAccount(exchange=self, paper= not private, credentials=credentials)
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


class PerpExchange(Exchange):
    def __init__(self, pairs, private, **credentials) -> None:
        super().__init__('kucoin', 'perp')
        self.symbols = self.translate_pairs(pairs)
        self.orderbookmanager = spot.SpotOrderbookManager(self.symbols)
        self.account = perp.PerpAccount(exchange=self, paper= not private, credentials=credentials)
        self.socket_token = None
        self._private = private
        if private:
            self.socket_token = self.account.get_socket_token()

    def get_orderbook_sbscription_message(self, symbols):
        topic = '/contractMarket/level2Depth50:' + ','.join(symbols)
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
        # print(msg)
        if not 'subject' in msg:
            return
        if msg['subject'] == 'level2':
            self.orderbookmanager.call_symbol_orderbooks(msg)

    def _start(self):
        print('Starting kucoin perp exchange')
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
