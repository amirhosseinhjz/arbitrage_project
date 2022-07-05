import abc
from dataclasses import dataclass
from .symbol_translator import symboltranslator
from .models import *
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
        asks = [self.ASK[price] for price in sorted(list(self.ASK.keys()))[:len]]
        if len == 1:
            return asks[0]
        return asks

    def bids(self, len):
        bids = [self.BID[price] for price in sorted(list(self.BID.keys()))[-len:][::-1]]
        if len == 1:
            return bids[0]
        return bids


class BaseOrderbookManager:
    def __init__(self) -> None:
        pass


class AccountManager:
    def __init__(self) -> None:
        self.position = None
        self.commision = 0.0
        self.paper = True
        self.trades = []

    @abc.abstractmethod
    def buy_wallet(self, symbol, price, qty):
        pass

    @abc.abstractmethod
    def sell_wallet(self, symbol, price, qty):
        pass

    def buy(self, symbol, price, quantity=None):
        if self.paper:
            return self._buy_papertrade(symbol, price, quantity)
        return self.buy_wallet(symbol, price, quantity)

    def sell(self, symbol, price, quantity=None):
        if self.paper:
            return self._sell_papertrade(symbol, price, quantity)
        return self.sell_wallet(symbol, price, quantity)

    @abc.abstractmethod
    def cancel_order(self, symbol, order_id):
        pass

    @abc.abstractmethod
    def account_callback(self, msg):
        pass

    def init_paper_mode(self):
        self._start_cash = 10000
        self._cash = 10000

    def _buy_papertrade(self, symbol, price, quantity=None):
        if self.position is None:
            self.position = self._open_position(
                'long', symbol, quantity, price)
            return self.position
        elif self.position.symbol == symbol and self.position.side == 'short':
            trade = self._close_position(self.position, price)
            self.position = None
            self.trades.append(trade)
            return trade

    def _sell_papertrade(self, symbol, price, quantity=None):
        if self.position is None:
            self.position = self._open_position(
                'short', symbol, quantity, price)
            return self.position
        elif self.position.symbol == symbol and self.position.side == 'long':
            trade = self._close_position(self.position, price)
            self.position = None
            self.trades.append(trade)
            return trade

    def _open_position(self, side, symbol, quantity, price):
        commision = self._calc_commision(price, quantity)
        self._update_cash('open', quantity, price, commision)
        return Position(symbol, price, quantity, commision, side, self.exchange)

    def _close_position(self, position: Position, price):
        position.exit_price = price
        commision = self._calc_commision(price, position.qty)
        position.exit_commission = commision
        position.profit_amount = position.qty * (price - position.entry_price) - (position.entry_commission + commision)
        position.profit_amount *= (-1 if position.side == 'short' else 1)
        position.profit_percent = position.profit_amount / position.entry_price
        self._update_cash('close', position.qty, position.exit_price, commision)
        return position

    def _update_cash(self, type, qty, price, commision=0.0):
        amount = qty * price
        if type == 'open':
            self._cash -= (amount + commision)
        elif type == 'close':
            self._cash += (amount - commision)

    def _calc_commision(self, price, qty):
        return price * qty * self.commision

    @property
    def in_position(self):
        return self.position is not None

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

    def buy(self, **kwargs):
        symbol = symboltranslator(self, kwargs['pair'][0], kwargs['pair'][1])
        price = kwargs['price']
        qty = kwargs.get('qty', None)
        return self.account.buy(symbol, price, qty)

    def sell(self, **kwargs):
        symbol = symboltranslator(self, kwargs['pair'][0], kwargs['pair'][1])
        price = kwargs['price']
        qty = kwargs.get('qty', None)
        return self.account.sell(symbol, price, qty)

    def __getattribute__(self, __name: str):
        try:
            return super().__getattribute__(__name)
        except AttributeError:
            try:
                return self.account.__getattribute__(__name)
            except AttributeError:
                raise AttributeError(__name)