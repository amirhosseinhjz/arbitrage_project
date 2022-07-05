import strategy
from orderbook import binance_manager, kucoin_manager
import pandas as pd



class Mytest(strategy.ArbitrageStrategy):
    def __init__(self, pairs):
        super().__init__(pairs)
        self.counters = {}
        binance_perp = binance_manager.PerpExchange(pairs, private=False)
        # binance_spot = binance_manager.SpotExchange(pairs, private=False)
        kucoin_perp = kucoin_manager.PerpExchange(pairs, private=False)
        self.min_open_diff_percent = 0.1
        self.min_close_diff_percent = 0.01
        self.exchanges = [kucoin_perp, binance_perp]

    def entry_condition(self, exchange1, exchange2, pair):
        ask1 = exchange1.get(pair).asks(1)
        ask2 = exchange2.get(pair).asks(1)
        bid1 = exchange1.get(pair).bids(1)
        bid2 = exchange2.get(pair).bids(1)

        diff1 = (bid2.price - ask1.price) / ask1.price * 100
        diff2 = (bid1.price - ask2.price) / ask2.price * 100

        if diff1 < self.min_open_diff_percent and diff2 < self.min_open_diff_percent:
            return False

        if diff1 > diff2:
            qty, price1, price2 = self.calc_qty(exchange1, exchange2, bid2, ask1)
            pos1 = exchange1.buy(pair=pair, price=price2, qty=qty)
            print(f'open: {pair}, {exchange1.name} buy {ask1.price}')
            pos2 = exchange2.sell(pair=pair, price=price1, qty=qty)
            print(f'open: {pair}, {exchange2.name} sell {bid1.price}')
            return exchange1, pos1, exchange2, pos2

        if diff2 > diff1:
            qty, price1, price2 = self.calc_qty(exchange1, exchange2, bid1, ask2)
            pos2 = exchange2.buy(pair=pair, price=price2, qty=qty)
            print(f'open: {pair}, {exchange2.name} buy {ask2.price}')
            pos1 = exchange1.sell(pair=pair, price=price1, qty=qty)
            print(f'open: {pair}, {exchange1.name} sell {bid1.price}')
            return exchange2, pos2, exchange1, pos1

        return False


    def exit_condition(self, bought_exchange, sold_exchange, pair):
        ask1 = bought_exchange.get(pair).asks(1)
        bid1 = sold_exchange.get(pair).bids(1)
        diff = (bid1.price - ask1.price) / ask1.price * 100
        if diff < self.min_close_diff_percent:
            bought_exchange.sell(pair=pair, price=ask1.price)
            print(f'close: {pair}, {bought_exchange.name} sell {ask1.price}')
            sold_exchange.buy(pair=pair, price=bid1.price)
            print(f'close: {pair}, {sold_exchange.name} buy {bid1.price}')
            return True
        return False



# if __name__ == '__main__':
#     pairs = [('ETH', 'USDT')]
#     strategy = Mytest(pairs)
#     strategy.start()

pairs = [('ETH', 'USDT'), ('BAT', 'USDT'), ('ALICE', 'USDT'), ('ADA', 'USDT'), 
        ('LINA', 'USDT'), ('EOS', 'USDT'), ('LIT', 'USDT'), ('RSR', 'USDT'), ('CELR', 'USDT'), ('UNI', 'USDT')]