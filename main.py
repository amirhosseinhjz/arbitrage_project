import orderbook.binance_orderbooks as binance
import orderbook.kucoin as kucoin
import time
import pandas as pd
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
    def __init__(self) -> None:
        pass

    def init_sockets(self):
        self.binance_spot = binance.SpotOrderbookManager(api_key, api_secret, symbols)
        self.binance_spot.start()
        self.binance_futures = binance.FuturesOrderbookManager(symbols)
        self.binance_futures.start()
        self.kucoin_spot = kucoin.SpotOrderbookManager(key, secret, passphrase, symbols)
        self.kucoin_spot.start()
        self.kucoin_futures = kucoin.FuturesOrderbookManager(key, secret, passphrase, kucoin_futures_symbs)
        self.kucoin_futures.start()

    def get_diffs_periodic(self):
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
            for j in range(len(symbols)):
                symbol = symbols[j]
                kucoin_fu_symbol = kucoin_futures_symbs[j]
                binance_spot_bid.extend(self.binance_spot.get(symbol.replace('-', '')).bids)
                binance_spot_ask.extend(self.binance_spot.get(symbol.replace('-', '')).asks)
                binance_futures_bid.extend(self.binance_futures.get(symbol.replace('-', '')).bids)
                binance_futures_ask.extend(self.binance_futures.get(symbol.replace('-', '')).asks)
                kucoin_spot_bid.extend(self.kucoin_spot.get(symbol).bids)
                kucoin_spot_ask.extend(self.kucoin_spot.get(symbol).asks)
                kucoin_futures_bid.extend(self.kucoin_futures.get(kucoin_fu_symbol).bids)
                kucoin_futures_ask.extend(self.kucoin_futures.get(kucoin_fu_symbol).asks)
            times.append(t)
            print(len(times))
                # bids.append([t]+ binance_spot_bid+ binance_futures_bid+ kucoin_spot_bid)
                # asks.append([t]+ binance_spot_ask+ binance_futures_ask+ kucoin_spot_ask)
            if len(times) > 1000:
                writer = pd.ExcelWriter(f'result{i}.xlsx', engine='xlsxwriter')
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
        time.sleep(10)
        self.get_diffs_periodic()


if __name__ == '__main__':
    main = Main()
    main.start()