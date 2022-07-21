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

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

@dataclass
class PositionPair:
    pair: tuple[str, str]
    long_exchange: str
    short_exchange: str
    long_position_entry_order: Order
    short_position_entry_order: Order
    long_position_exit_order: Order = None
    short_position_exit_order: Order = None

    def __str__(self):
        return f'{self.buy_exchange} {self.buy_position} {self.sell_exchange} {self.sell_position}'

    def __repr__(self) -> str:
        return self.__str__()

    # def calc_profit(self):
    #     self.profit_amount = self.sell_position.profit_amount + \
    #         self.buy_position.profit_amount

