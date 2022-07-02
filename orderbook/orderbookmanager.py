import abc

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
        self.ASK = dict()
        self.BID = dict()
        
    @abc.abstractmethod
    def get_snapshot(self):
        pass
    
    def callback(self, msg):
        pass

    def asks(self, len):
        return [self.ASK[price].list() for price in sorted(list(self.ASK.keys()))[:len]]

    @property
    def bids(self, len):
        return [self.BID[price].list() for price in sorted(list(self.BID.keys()))[-len][::-1]]

class BaseOrderbookManager:
    pass