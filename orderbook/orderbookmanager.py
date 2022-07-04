import abc
from .symbol_translator import symboltranslator
ASK = 'ASK'
BID = 'BID'

class OrderBook:

    def __init__(self, update_time, price, qty):
        self.update_time = update_time
        self.price = price
        self.qty = qty

    @staticmethod
    def create(update_time, price, qty):
        return OrderBook(update_time, price, qty)

    def __str__(self):
        return str(self.update_time) + ', ' + str(self.price) + ', ' + str(self.qty)
    
    def list(self):
        return [self.update_time, self.price, self.qty]

    def __repr__(self) -> str:
        pass

    # overroide subtraction method
    def __sub__(self, other):
        return OrderBook.create(self.update_time-other.update_time, 100*(self.price - other.price)/self.price, self.qty - other.qty)
        # return f'TimeDiff: {self.update_time - other.update_time}, PriceDiff%: {100*(self.price - other.price)/self.price}, QtyDiff: {self.qty - other.qty}'

class Orderbooks:
    def __init__(self, symbol, depth=5):
        self.symbol = symbol
        self.depth = depth
        self.ASK = dict()
        self.BID = dict()

    def create_orderbook(self, update_time, price, qty, type):
        orderbook_dict = getattr(self, type)
        if qty == 0:
            if price in orderbook_dict.keys():
                del orderbook_dict[price]
            return
        if price in orderbook_dict:
            orderbook_dict[price].update_time = update_time
            orderbook_dict[price].qty = qty
            return
        orderbook_dict[price] = OrderBook(update_time, price, qty)


    def reset_orderbooks(self):
        self.ASK.clear()
        self.BID.clear()
        
    @abc.abstractmethod
    def get_snapshot(self):
        pass
    
    @abc.abstractmethod
    def callback(self, msg):
        pass

    def asks(self, len):
        return [self.ASK[price] for price in sorted(list(self.ASK.keys()))[:len]]

    def bids(self, len):
        return [self.BID[price] for price in sorted(list(self.BID.keys()))[-len:][::-1]]

class BaseOrderbookManager:
    def __init__(self) -> None:
        pass


class AccountManager:
    def __init__(self) -> None:
        pass

    @abc.abstractmethod
    def send_order(self, symbol, side, price, qty):
        pass

    @abc.abstractmethod
    def cancel_order(self, symbol, order_id):
        pass

    @abc.abstractmethod
    def account_callback(self, msg):
        pass

class Exchange:
    def __init__(self, exchange, market_type) -> None:
        self.exchange = exchange
        self.market_type = market_type
        self.name = exchange + '_' + market_type

    def translate_pairs(self, pairs):
        return [symboltranslator(self, pair[0], pair[1]) for pair in pairs]

    def get(self, pair):
        symbol = symboltranslator(self, pair[0], pair[1])
        return self.orderbookmanager(symbol)