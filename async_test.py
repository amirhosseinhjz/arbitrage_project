from async_strategy import ArbitrageStrategy
from orderbook import kucoin_manager, binance_manager
from orderbook.models import *



class Strategy(ArbitrageStrategy):
    def __init__(self, pairs):
        super().__init__(pairs)
        API_KEY = '93a09d317e3c3d6a986401c1ad487d81f8c53a50122f3a91a0610fe9880b884d' # futures testnet
        API_SECRET = '286e0fca8d36061c20f0dc53ef7a31c670ee8a993cc63c90c1cea9cfdfab764b'
        binance_creds = {'api_key': API_KEY, 'api_secret': API_SECRET}
        binance_perp = binance_manager.PerpExchange(pairs=pairs, credentials=binance_creds, testnet=True, private=True)
        key = '62d254194deedd0001e77cf3' #kucoin futures
        secret = 'bfa00f13-7103-4e5a-890b-165b520cd77a'
        passphrase = 'noatrader'
        creds = {'api_key':key, 'api_secret':secret, 'api_passphrase':passphrase}
        kucoin_perp = kucoin_manager.PerpExchange(pairs=pairs, credentials=creds, testnet=False, private=True)
        self.exchanges = [kucoin_perp, binance_perp]
        self.min_open_diff_percent = 0.05
        self.min_close_diff_percent = 0.01
        self.counter = 0


    def entry_condition(self, pair, exchange1, exchange2):
        ask1 = exchange1.asks(pair) # ask1 is the ask price of exchange1
        ask2 = exchange2.asks(pair) # ask2 is the ask price of exchange2
        bid1 = exchange1.bids(pair) # bid1 is the bid price of exchange1
        bid2 = exchange2.bids(pair) # bid2 is the bid price of exchange2
        diff1 = (bid2.price - ask1.price) / ask1.price * 100 # diff percent between exchange1 and exchange2
        diff2 = (bid1.price - ask2.price) / ask2.price * 100 # diff percent between exchange2 and exchange1

        if diff1 < self.min_open_diff_percent and diff2 < self.min_open_diff_percent: # if both diff are less than min_open_diff_percent
            return False

        if diff1 > diff2:
            qty, price1, price2 = self.calc_qty(exchange1, exchange2, bid2, ask1) # qty: size of position calculated by free assets and orderbooks
            long_id = exchange1.buy(pair=pair, price=price2, qty=qty) # buy on exchange1
            print(f'open: {pair}, {exchange1.name} buy {ask1.price}')
            short_id = exchange2.sell(pair=pair, price=price1, qty=qty) # sell on exchange2
            print(f'open: {pair}, {exchange2.name} sell {bid1.price}')
            return exchange1, exchange2, long_id, short_id

        if diff2 > diff1:
            qty, price1, price2 = self.calc_qty(exchange1, exchange2, bid1, ask2)
            long_id = exchange2.buy(pair=pair, price=price1, qty=qty)
            print(f'open: {pair}, {exchange2.name} buy {ask2.price}')
            short_id = exchange1.sell(pair=pair, price=price2, qty=qty)
            print(f'open: {pair}, {exchange1.name} sell {bid2.price}')
            return exchange2, exchange1, long_id, short_id

        return False


    def entry_order_check_condition(self, positionpair: PositionPair):
        order1 = positionpair.long_position_entry_order # long_position_entry_order
        order2 = positionpair.short_position_entry_order # short_position_entry_order
        if order1.status == 'FILLED' and order2.status == 'FILLED':
            print(f'open: {positionpair.pair}, {positionpair.long_exchange.name} buy {order1.price} FILLED')
            print(f'open: {positionpair.pair}, {positionpair.short_exchange.name} sell {order2.price} FILLED')
            return True

        # manage partially filled and cancelled orders with timeout

    def exit_condition(self, positionpair: PositionPair):
        pair = positionpair.pair
        long_exchange = positionpair.long_exchange
        short_exchange = positionpair.short_exchange
        asks1 = long_exchange.asks(pair)
        bids2 = short_exchange.bids(pair)

        diff = (bids2.price - asks1.price) / asks1.price * 100
        if diff <= self.min_close_diff_percent: # if diff is less than min_close_diff_percent close the position
            id1 = long_exchange.sell(pair=pair, price=asks1.price, qty=asks1.qty) # sell on exchange1
            id2 = short_exchange.buy(pair=pair, price=bids2.price, qty=bids2.qty) # buy on exchange2
            print(f'close: {pair}, {long_exchange.name} sell {asks1.price}')
            print(f'close: {pair}, {short_exchange.name} buy {bids2.price}')
            return id1, id2

    def exit_order_check_condition(self, positionpair: PositionPair):
        order1 = positionpair.long_position_exit_order
        order2 = positionpair.short_position_exit_order
        if order1.status == 'FILLED' and order2.status == 'FILLED':
            print(f'close: {positionpair.pair}, {positionpair.long_exchange.name} sell {order1.price} FILLED')
            print(f'close: {positionpair.pair}, {positionpair.short_exchange.name} buy {order2.price} FILLED')
            return True
