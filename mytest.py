from arbitrage_strategy import *
from arbitrage_strategy.orderbook import binance_manager, kucoin_manager
import pandas as pd



class Mytest(strategy.ArbitrageStrategy):
    def __init__(self, pairs):
        super().__init__(pairs)
        binance_spot = binance_manager.PerpExchange(pairs, private=False)
        kucoin_spot = kucoin_manager.PerpExchange(pairs, private=False)
        self.exchanges = [binance_spot, kucoin_spot]
        self.df_data = {pair:[] for pair in pairs}

    def conditions(self, exchange1, exchange2, pair):
        # ask1 = exchange1.get(pair).asks(1)[0]
        ask2 = exchange2.get(pair).asks(1)[0]
        bid1 = exchange1.get(pair).bids(1)[0]
        # bid2 = exchange2.get(pair).bids(1)[0]
        self.df_data[pair].append([exchange1.name, exchange2.name]+(bid1-ask2).list())
        # self.df_data[pair].append([exchange2.name, exchange1.name]+(bid2-ask1).list())
        if len(self.df_data[pair]) > 300:
            self.save_df(pair)
        # print(pair, exchange1.name, exchange2.name, ': ', bid1-ask2)
        # print(pair, exchange2.name, exchange1.name, ': ', bid2-ask1)


    def save_df(self, pair):
        data, self.df_data[pair] = self.df_data[pair], []
        df = pd.DataFrame(data, columns=['exchange1', 'exchange2', 'timeDiff', 'priceDiff%', 'qtyDiff'])
        df.to_csv(f'{pair}.csv', index=False)



if __name__ == '__main__':
    pairs = [('ETH', 'USDT'), ('BAT', 'USDT'), ('ALICE', 'USDT'), ('ADA', 'USDT'), 
        ('LINA', 'USDT'), ('EOS', 'USDT'), ('LIT', 'USDT'), ('RSR', 'USDT'), ('CELR', 'USDT'), ('UNI', 'USDT')]
    strategy = Mytest(pairs)
    strategy.start()