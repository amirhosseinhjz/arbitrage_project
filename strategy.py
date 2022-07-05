import asyncio
import orderbook
from orderbook.orderbookmanager import OrderBook
import threading
import time
import abc
import time
from itertools import combinations, permutations
from orderbook.symbol_translator import symboltranslator
from orderbook.models import *
import pandas as pd

class ArbitrageStrategy:

    @abc.abstractmethod
    def __init__(self, pairs):
        self.running = False
        self.pairs = pairs
        self.exchanges = []
        self._open_positions = {}
        self._closed_positions = []

    def validate_pairs(self, exchanges, pairs):
        """
        Remove pairs that are not supported by any of the exchanges
        """
        validated_pairs = []
        for pair in pairs:
            for exchange in exchanges:
                if not symboltranslator.has_pair(exchange, pair):
                    continue
            validated_pairs.append(pair)
        return validated_pairs

    @abc.abstractmethod
    def entry_condition(self, exchange1, exchange2, pair):
        """"
        write this function to implement your arbitrage strategy

        if no position opened False should be returned
        if a position is opened the data below should be retourned in the shown order:
            [
            buy_exchange: exchange in which the long position is opened,
            buy_position: the opsition object which exchange 1 returned,
            sell_exchange: exchange in which the short position is opened,
            sell_position: the opsition object which exchange 2 returned,
            ]
        """
        return False

    @abc.abstractmethod
    def exit_condition(self, buy_exchange, sell_exchange, pair):
        """"
        write this function to implement your arbitrage strategy
        if no position closed False should be returned,
        if a position is closed True should be returned.
        """
        return False

    @staticmethod
    def calc_permutations(exchanges):
        exchange_combinations = list(combinations(exchanges, 2))
        return exchange_combinations

    @classmethod
    def calc_qty(cls, exchange1, exchange2, orderbooks1, orderbooks2):
        """
        Calculate the possible amount of currency to buy/sell to arbitrage
        """
        qty1, avg_price1 = ArbitrageStrategy.aggregate_orderbooks(orderbooks1)
        qty2, avg_price2 = ArbitrageStrategy.aggregate_orderbooks(orderbooks2)
        exchange1_max_qty = exchange1.account._cash / avg_price1
        exchange2_max_qty = exchange2.account._cash / avg_price2
        return min(qty1, qty2, exchange1_max_qty, exchange2_max_qty), avg_price1, avg_price2

    @staticmethod
    def aggregate_orderbooks(orderbooks):
        """
        Aggregate list of orderbooks into one orderbook
        """
        if isinstance(orderbooks, OrderBook):
            return orderbooks.qty, orderbooks.price
        qty = sum([orderbook.qty for orderbook in orderbooks])
        avg_price = sum(
            [orderbook.price * orderbook.qty for orderbook in orderbooks]) / qty
        return qty, avg_price

    def condition_thread(self, exchange1, exchange2, pairs):
        while True:
            for pair in pairs:

                key = ArbitrageStrategy._hash(exchange1, exchange2, pair)
                positionpair = self._open_positions.get(key, None)
                if positionpair:
                    result = self.exit_condition(positionpair.buy_exchange, positionpair.sell_exchange, pair)
                    if result:
                        positionpair.calc_profit()
                        self._closed_positions.append(positionpair)
                        del self._open_positions[key]
                else:
                    if exchange1.account.in_position or exchange2.account.in_position:
                        continue
                    result = self.entry_condition(exchange1, exchange2, pair)
                    if result:
                        self._open_positions[key] = PositionPair(*result)
            time.sleep(1)

    @staticmethod
    def _hash(exchange1, exchange2, pair):
        return exchange1.name + exchange2.name + str(pair)

    def start(self, wait_time=15):
        if self.running:
            print('Strategy already running!!!')
            return
        self.running = True
        print('Waiting for exchanges sockets to start...')
        for exchange in self.exchanges:
            exchange.start()
        print(f'Sleep for {wait_time} seconds...')
        time.sleep(wait_time)
        self.threads = []
        exchange_pair_permutations = self.calc_permutations(self.exchanges)
        print('\nStarting strategy...')
        for exchange1, exchange2 in exchange_pair_permutations:
            thread = threading.Thread(target=self.condition_thread, args=(
                exchange1, exchange2, self.pairs))
            thread.start()
            self.threads.append(thread)

    @property
    def open_positions(self):
        if self._open_positions:
            open_positions = self._open_positions.values()
            return pd.DataFrame(open_positions)

    @property
    def closed_positions(self):
        if self._closed_positions:
            closed_positions = self._closed_positions.copy()
            return pd.DataFrame(closed_positions)

    @property
    def result(self):
        result = {}
        closed_positions = self._closed_positions.copy()
        result['number_of_trades'] = len(closed_positions)
        result['number_of_winning_trades'] = len([position for position in closed_positions if position.profit_amount > 0])
        result['number_of_losing_trades'] = len([position for position in closed_positions if position.profit_amount < 0])
        result['profit_amount'] = sum([position.profit_amount for position in closed_positions])
        result['profit_percentage'] = result['profit_amount'] / sum([exchange.account._start_cash for exchange in self.exchanges]) * 100
        result['number_of_open_positions'] = len(self._open_positions)
        return result




























    # async def _enter(self, pair, exchange1, exchange2, asks1, bids2):
    #     """
    #     Enter arbitrage position
    #     """
    #     if exchange1.account.in_position or exchange2.account.in_position:
    #         return
    #     qty, avg_price1, avg_price2 = await self.calc_qty(exchange1, exchange2, asks1, bids2)
    #     if qty == 0:
    #         return
    #     position1 = await exchange1.buy(price=avg_price2, pair=pair, qty=qty)
    #     position2 = await exchange2.sell(price=avg_price1, pair=pair, qty=qty)
    #     return PositionPair(exchange1, position1, exchange2, position2)

    # def entry(self, pair, exchange1, exchange2, asks1, bids2):
    #     """
    #     Execute arbitrage order 
    #     """
    #     positionpair = asyncio.run(self._enter(pair, exchange1, exchange2, asks1, bids2))
    #     if positionpair is not None:
    #         hashed_name = ArbitrageStrategy.hash_arbitrage_position(exchange1, exchange2, pair)
    #         self._open_positions[hashed_name] = positionpair
    #         return positionpair

    # async def _exit(self, positionpair):
    #     """
    #     Exit arbitrage position
    #     """
    #     buy_exchange, buy_position, sell_exchange, sell_position = positionpair
    #     if not buy_exchange.account.in_position or not sell_exchange.account.in_position:
    #         return
    #     await exchange1.sell(position1)
    #     await exchange2.buy(position2)
    #     hashed_name = ArbitrageStrategy.hash_arbitrage_position(buy_exchange, sell_exchange, buy_position.symbol)
    #     del self.positions[hashed_name]

    # def exit(self, positionpair, price1, price2):
    #     """
    #     Exit arbitrage position
    #     """
    #     asyncio.run(self._exit(positionpair))
    #     return positionpair

