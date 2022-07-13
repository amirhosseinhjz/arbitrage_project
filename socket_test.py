# from orderbook import binance_manager
# API_KEY = '93a09d317e3c3d6a986401c1ad487d81f8c53a50122f3a91a0610fe9880b884d' # futures testnet^M
# API_SECRET = '286e0fca8d36061c20f0dc53ef7a31c670ee8a993cc63c90c1cea9cfdfab764b'
# creds = {'api_key':API_KEY, 'api_secret':API_SECRET}
# pairs = ('ETH', 'USDT'), ('BAT', 'USDT'), ('ALICE', 'USDT'), ('ADA', 'USDT')
# bm = binance_manager.PerpExchange(pairs=pairs, private=True, credentials=creds, testnet=True)
# thrd = bm.start()
# thrd.join()

from binance.client import Client
from binance import ThreadedWebsocketManager

API_KEY = '93a09d317e3c3d6a986401c1ad487d81f8c53a50122f3a91a0610fe9880b884d' # futures testnet^M
API_SECRET = '286e0fca8d36061c20f0dc53ef7a31c670ee8a993cc63c90c1cea9cfdfab764b'
client = Client(API_KEY, API_SECRET, testnet=True)
listenkey = client.futures_stream_get_listen_key()
print(listenkey)
twm = ThreadedWebsocketManager(API_KEY, API_SECRET, testnet=True)
twm.start()
twm.start_futures_multiplex_socket(callback=print, streams=['btcusdt@kline_1m', listenkey])
twm.join()