import abc
from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    entry_price: float
    qty: float
    entry_commission: float
    side: str
    exchange: str
    exit_price: float = 0
    exit_commission: float = 0
    profit_percent: float = 0
    profit_amount: float = 0

    def __str__(self):
        return f'{self.symbol} {self.qty} @ {self.price}'


@dataclass
class PositionPair:
    buy_exchange: str
    buy_position: Position
    sell_exchange: str
    sell_position: Position
    profit_amount: float = 0

    def __str__(self):
        return f'{self.buy_exchange} {self.buy_position} {self.sell_exchange} {self.sell_position}'

    def __repr__(self) -> str:
        return self.__str__()

    def calc_profit(self):
        self.profit_amount = self.sell_position.profit_amount + \
            self.buy_position.profit_amount


@dataclass
class Order:
    updatetime: int
    id: int
    symbol: str
    price: float
    quantity: float
    side: str
    status: str
    executed_quantity: float = 0
    avg_price: float = 0

    def __str__(self):
        return f'{self.side}: {self.quantity} @ {self.price}'