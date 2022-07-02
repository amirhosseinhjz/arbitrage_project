import threading
import orderbook.binance_orderbooks as binance
import orderbook.kucoin as kucoin
import time
import pandas as pd
from orderbook.symbol_translator import symboltranslator
import threading
symbols = ['BTC-USDT']#, 'ETH-USDT']
kucoin_futures_symbs = ['XBTUSDTM']

# kucoin
key = '623053d4b7199e00015325ed'
secret = 'da926127-2c9f-4af9-a2dd-1de4f7681c63'
passphrase = '12561256'

# binance
api_key = 'gcJLtOs6tZYTOBEyIYY0JZBDagmFMkc5SY5T8R792cCUgBn7YCLfG7pOJZG3J36x'
api_secret = 'EYyaqoqRyPxozdDQQmlL7xQiHaqDIxgGAav68UoYAznTAOI6darEG132kavhI3Vh'


class Main:
    def __init__(self, pairs) -> None:
        self.pairs = pairs

    def init_sockets(self):
        self.binance_spot = binance.SpotOrderbookManager(api_key, api_secret, self.pairs)
        self.binance_spot.start()
        self.binance_futures = binance.FuturesOrderbookManager(self.pairs)
        self.binance_futures.start()
        self.kucoin_spot = kucoin.SpotOrderbookManager(key, secret, passphrase, self.pairs)
        self.kucoin_spot.start()
        self.kucoin_futures = kucoin.FuturesOrderbookManager(key, secret, passphrase, self.pairs)
        self.kucoin_futures.start()

    def get_diffs_periodic(self, pair):
        binance_spot_symbol = symboltranslator('binance', pair[0], pair[1], 'spot')
        binance_futures_symbol = symboltranslator('binance', pair[0], pair[1], 'perp')
        kucoin_spot_symbol = symboltranslator('kucoin', pair[0], pair[1], 'spot')
        kucoin_futures_symbol = symboltranslator('kucoin', pair[0], pair[1], 'perp')

        times = []
        binance_spot_bid = []
        binance_spot_ask = []
        binance_futures_bid = []
        binance_futures_ask = []
        kucoin_spot_bid = []
        kucoin_spot_ask = []
        kucoin_futures_bid = []
        kucoin_futures_ask = []

        i = 0
        while True:
            # print('Working...')
            t = int(time.time())
            binance_spot_bid.extend(self.binance_spot.get(binance_spot_symbol).bids)
            binance_spot_ask.extend(self.binance_spot.get(binance_spot_symbol).asks)
            binance_futures_bid.extend(self.binance_futures.get(binance_futures_symbol).bids)
            binance_futures_ask.extend(self.binance_futures.get(binance_futures_symbol).asks)
            kucoin_spot_bid.extend(self.kucoin_spot.get(kucoin_spot_symbol).bids)
            kucoin_spot_ask.extend(self.kucoin_spot.get(kucoin_spot_symbol).asks)
            kucoin_futures_bid.extend(self.kucoin_futures.get(kucoin_futures_symbol).bids)
            kucoin_futures_ask.extend(self.kucoin_futures.get(kucoin_futures_symbol).asks)
            times.append(t)
            print(pair, ' : ', len(times))
            if len(times) > 500:
                writer = pd.ExcelWriter(binance_spot_symbol+f'_{i}.xlsx', engine='xlsxwriter')
                pd.DataFrame(binance_spot_bid, columns=['time', 'price', 'size']).to_excel(writer, startcol=1, startrow=1, index=False)
                pd.DataFrame(binance_spot_ask, columns=['time', 'price', 'size']).to_excel(writer, startcol=5, startrow=1, index=False)
                pd.DataFrame(binance_futures_bid, columns=['time', 'price', 'size']).to_excel(writer, startcol=9, startrow=1, index=False)
                pd.DataFrame(binance_futures_ask, columns=['time', 'price', 'size']).to_excel(writer, startcol=13, startrow=1, index=False)
                pd.DataFrame(kucoin_spot_bid, columns=['time', 'price', 'size']).to_excel(writer, startcol=17, startrow=1, index=False)
                pd.DataFrame(kucoin_spot_ask, columns=['time', 'price', 'size']).to_excel(writer, startcol=21, startrow=1, index=False)
                pd.DataFrame(kucoin_futures_bid, columns=['time', 'price', 'size']).to_excel(writer, startcol=25, startrow=1, index=False)
                pd.DataFrame(kucoin_futures_ask, columns=['time', 'price', 'size']).to_excel(writer, startcol=29, startrow=1, index=False)
                worksheet = writer.sheets['Sheet1']
                worksheet.write_string(0, 0, 'times')
                worksheet.write_string(0, 1, 'binance_spot_bid')
                worksheet.write_string(0, 5, 'binance_spot_ask')
                worksheet.write_string(0, 9, 'binance_futures_bid')
                worksheet.write_string(0, 13, 'binance_futures_ask')
                worksheet.write_string(0, 17, 'kucoin_spot_bid')
                worksheet.write_string(0, 21, 'kucoin_spot_ask')
                worksheet.write_string(0, 25, 'kucoin_futures_bid')
                worksheet.write_string(0, 29, 'kucoin_futures_ask')
                k = 2
                for t_ in times:
                    worksheet.write_string(k, 0, str(t_))
                    k += 5
                writer.save()
                times = []
                binance_spot_bid = []
                binance_spot_ask = []
                binance_futures_bid = []
                binance_futures_ask = []
                kucoin_spot_bid = []
                kucoin_spot_ask = []
                kucoin_futures_bid = []
                kucoin_futures_ask = []
                i += 1
            else: time.sleep(1)

    def start(self):
        self.init_sockets()
        time.sleep(30)
        self.threads = []
        for pair in self.pairs:
            thread = threading.Thread(target=self.get_diffs_periodic, args=(pair,))
            self.threads.append(thread)
            thread.start()
            time.sleep(1)


if __name__ == '__main__':
    pairs = [('ETH', 'USDT'), ('BAT', 'USDT'), ('ALICE', 'USDT'), ('ADA', 'USDT'), 
        ('LINA', 'USDT'), ('EOS', 'USDT'), ('LIT', 'USDT'), ('RSR', 'USDT'), ('CELR', 'USDT'), ('UNI', 'USDT')]
    main = Main(pairs=pairs)
    main.start()