import asyncio
import websockets
import threading
import requests
import json
import random

class Socket:
    def __init__(self, url, callback, messages=[]):
        print(url)
        self.url = url
        self.callback = callback
        self.messages_on_start = messages
        self._socket = None

    async def start_socket(self):
        try:
        # if True:
            async with websockets.connect(self.url, close_timeout=0.1) as websocket:
                self._socket = websocket
                while True:
                    while self.messages:
                        await self._send_msg(self.messages.pop(0))
                    message = await websocket.recv()
                    self._callback(json.loads(message))
        except Exception as e:
            print("Error: ", e)
            self.start()

    def _callback(self, message):
        self.callback(message)

    def _start(self):
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)
        # import nest_asyncio
        # nest_asyncio.apply()
        self.messages = self.messages_on_start.copy()
        asyncio.get_event_loop().run_until_complete(self.start_socket())

    def start(self, multithread=False):
        if multithread:
            self.thread = threading.Thread(target=self._start)
            self.thread.start()
            return
        self._start()

    async def _send_msg(self, message):
        if self._socket:
            await self._socket.send(message)

    def send_msg(self, message):
        asyncio.get_event_loop().run_until_complete(self._send_msg(message))

    def join(self):
        self.thread.join()

class RestApiUrl:
    KUCOIN_SPOT_URL = 'https://api.kucoin.com'
    KUCOIN_PERP_URL = 'https://api-futures.kucoin.com'

class WebsocketManager:
    BINANCE_SPOT_BASE_URL = 'wss://stream.binance.com:9443'
    BINANCE_PERP_BASE_URL = 'wss://fstream.binance.com'
    BINANCE_PERP_BASE_URL_TESTNET = 'wss://stream.binancefuture.com'
    KUCOIN_SPOT_BASE_URL = 'wss://ws-api.kucoin.com/endpoint'
    KUCOIN_PERP_BASE_URL = 'wss://ws-api.kucoin.com/endpoint'
    # BITFINEX_BASE_URL = 'wss://api-pub.bitfinex.com/ws/'


    @classmethod
    def create(cls, **kwargs):#exhange, type, callback, streams=[], messages=[]):
        exchange = kwargs['exchange']
        type = kwargs['type']
        url_creator = getattr(cls, exchange + '_' + type + '_url')
        url = url_creator(**kwargs)
        if 'messages' in kwargs:
            messages = kwargs['messages']
        else:
            messages = []
        return Socket(url, kwargs['callback'], messages)

    @staticmethod
    def binance_spot_url(**kwargs):
        streams = kwargs['streams']
        return WebsocketManager.BINANCE_SPOT_BASE_URL + '/stream?streams=' + '/'.join(streams)

    @staticmethod
    def binance_perp_url(**kwargs):
        streams = kwargs.get('streams', None)
        testnet = kwargs.get('testnet', False)
        listenkey = kwargs.get('listenkey', None)
        url = WebsocketManager.BINANCE_PERP_BASE_URL if not testnet else WebsocketManager.BINANCE_PERP_BASE_URL_TESTNET 
        # url += '/ws/'
        if streams:
            url += '/stream?streams=' + '/'.join(streams)
            if listenkey:
                url += '/' + listenkey #'&listenKey='
            return url
        if listenkey:
            url += '/ws/'+listenkey
        return url

    @staticmethod
    def kucoin_spot_url(**kwargs):
        """
        wss://ws-api.kucoin.com/endpoint?
        token=2neAiuYvAU61ZDXANAGAsiL4-iAExhsBXZxftpOeh_55i3Ysy2q2LEsEWU64mdzUOPusi34M_wGoSf7iNyEWJz-1zXC0KL3PHtO56tnZF5uezgujw0ePOtiYB9J6i9GjsxUuhPw3BlrzazF6ghq4L7ShKwrLxFVWfVv
        cXrl4HZk=.HpBV3gQN9qZenbo1WRHgHQ==&connectId=1656911999626"""
        token = kwargs.get('token', None)
        connectId = kwargs.get('connectId', None)
        if token is None:
            token = requests.post(RestApiUrl.KUCOIN_SPOT_URL + '/api/v1/bullet-public').json()['data']['token']
        if connectId is None:
            connectId = str(random.randint(1, 1000000))
        return WebsocketManager.KUCOIN_SPOT_BASE_URL + '?token=' + token + '&connectId=' + connectId

    @staticmethod
    def kucoin_perp_url(**kwargs):
        token = kwargs.get('token', None)
        connectId = kwargs.get('connectId', None)
        if token is None:
            token = requests.post(RestApiUrl.KUCOIN_PERP_URL + '/api/v1/bullet-public').json()['data']['token']
        if connectId is None:
            connectId = str(random.randint(1, 1000000))
        return WebsocketManager.KUCOIN_PERP_BASE_URL + '?token=' + str(token) + '&connectId=' + str(connectId)