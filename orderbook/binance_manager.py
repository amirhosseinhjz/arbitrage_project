from .orderbookmanager import *
from .exchange.binance import spot, perp
import time
import threading
import asyncio
from .symbol_translator import symboltranslator
import requests
from .socketmanager import WebsocketManager


class SpotExchange(Exchange):
    def __init__(self, pairs, private, **credentials) -> None:
        super().__init__('binance', 'spot')
        self.symbols = self.translate_pairs(pairs)
        self.orderbookmanager = spot.SpotOrderbookManager(self.symbols)
        self.streams = self.get_streams()
        self.account = spot.SpotAccount(exchange=self, paper= not private, credentials=credentials)
        if private:
            listenkey = self.account.get_listenkey()
            self.streams.append(listenkey)

    def get_streams(self):
        return [f'{symbol.lower()}@depth@100ms' for symbol in self.symbols]

    def start_socket(self):
        socket = WebsocketManager.create(
            exchange='binance', type='spot', streams=self.streams, callback=self.socket_callback)
        socket.start(multithread=False)

    def socket_callback(self, msg):
        # print(msg)
        if not 'data' in msg:
            return
        msg = msg['data']
        # print(msg['e'])
        if msg['e'] == 'depthUpdate':
            self.orderbookmanager.call_symbol_orderbooks(msg)

    def _start(self):
        print('Starting binance spot exchange')
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
    def __init__(self, pairs, private=False, credentials=None) -> None:
        super().__init__('binance', 'perp')
        self.symbols = self.translate_pairs(pairs)
        self.orderbookmanager = perp.PerpOrderbookManager(self.symbols)
        self.streams = self.get_streams()
        self.account = perp.PerpAccount(exchange=self, paper= not private, credentials=credentials)
        if private:
            listenkey = self.account.get_listenkey()
            self.streams.append(listenkey)

    def get_streams(self):
        return [f'{symbol.lower()}@depth@100ms' for symbol in self.symbols]

    def start_socket(self):
        socket = WebsocketManager.create(
            exchange='binance', type='perp', streams=self.streams, callback=self.socket_callback)
        socket.start(multithread=False)

    def socket_callback(self, msg):
        msg = msg['data']
        if msg['e'] == 'depthUpdate':
            self.orderbookmanager.call_symbol_orderbooks(msg)

    def _start(self):
        print('Starting binance perp exchange')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.orderbookmanager._init_orderbooks()
        self.start_socket()

    def start(self):
        import nest_asyncio
        nest_asyncio.apply()
        thread = threading.Thread(target=self._start)
        thread.start()

    def stop(self):
        self.twm.stop()
