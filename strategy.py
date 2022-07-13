import asyncio

from importlib_metadata import entry_points
import orderbook
from orderbook.orderbookmanager import OrderBook
import threading
import time
import abc
import time
from itertools import combinations, permutations
import itertools
from orderbook.symbol_translator import symboltranslator
from orderbook.models import *
import pandas as pd
from exchange_pair_dict import ExchangePairDict
# permutations = itertools.chain(
# itertools.product(long_ent_type, long_close_type, short_ent_type, short_close_type, hl_len, hi_ma_len, sl_input,
#                   hma_len, hma2_len, min_profit, constant_stop_loss, src_hma_len,hl_lookback_len,hmac_len))


class ArbitrageStrategy:

    @abc.abstractmethod
    def __init__(self, pairs):
        self._running = False
        self.pairs = pairs
        self.exchanges = []
        self._open_positions = {}
        self._closed_positions = []

    def _init_before_start(self):
        self.lock = threading.Lock()
        self.neutral_pairs = ExchangePairDict()
        self.entry_orders = ExchangePairDict()
        self.positions = ExchangePairDict()
        self.exit_orders = ExchangePairDict()
        exchange_permutations = self.calc_permutations(self.exchanges)
        pairs = self.validate_pairs(self.exchanges, self.pairs)
        exchanges_pairs = list(itertools.chain(
            itertools.product(pairs, exchange_permutations)))
        for (exchange1, exchange2), pair in exchanges_pairs:
            self.neutral_pairs.add(exchange1, exchange2, pair)

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
    def entry_condition(self, pair, exchange1, exchange2):
        """"
        write this function to implement your arbitrage strategy

        if no change made, return False
        if an order is sent the data below should be returned in the shown order:
            [
            buy_exchange: exchange in which the long order is sent,
            buy_order_id: order id of the long position,
            sell_exchange: exchange in which the short order is sent,
            sell_order_id: order id of the short position
            ]
        """
        return False

    def entry_order_check_condition(self, pair, buy_order_exchange, sell_order_exchange, buy_order_id, sell_order_id):
        """
        write this function to manage orders to be filled or killed
        if no change made, False should be returned
        if filled, the data below should be returned in the shown order:
            [
            "filled",
            buy_exchange: exchange in which the long order is filled,
            buy_position: position object of the long position,
            sell_exchange: exchange in which the short order is filled,
            sell_position: position object of the short position.
            ]
        if orders are cancelled, the data below should be returned in the shown order:
            [
            "cancelled",
            exchnge1: exchange in which the long order is cancelled,
            exchange2: exchange in which the short order is cancelled,
            ]
        """
        return False

    @abc.abstractmethod
    def exit_condition(self, pair, buy_exchange, sell_exchange):
        """
        write this function to implement your arbitrage strategy
        if no position closed False should be returned,
        if a position is closed the data below should be returned in the shown order:
            [
            buy_exchange: exchange in which the long position is closed,
            sell_order_id: order id of the long close order,
            sell_exchange: exchange in which the short position is closed,
            buy_order_id: order id of the short close order,
            ]
        """
        return False

    @abc.abstractmethod
    def exit_order_check_condition(self, pair, buy_exchange, sell_exchange, buy_order_id, sell_order_id):
        """
        write this function to manage orders to be filled or killed
        if no change made, False should be returned
        if filled, the data below should be returned in the shown order:
            [
            "filled",
            buy_exchange: exchange in which the long order is filled,
            buy_position: position object of the long position,
            sell_exchange: exchange in which the short order is filled,
            sell_position: position object of the short position.
            ]
        if orders are cancelled, the data below should be returned in the shown order:
            [
            "cancelled": True,
            exchnge1: exchange in which the long order is cancelled,
            exchange2: exchange in which the short order is cancelled,
            ]
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

    def entry_cond_execution(self):
        """
        Execute the entry condition for all pairs
        """
        while True:
            with self.lock:
                exchange_pairs = self.neutral_pairs.copy()
            for key, data in exchange_pairs.items():
                pair, exchange1, exchange2 = data
                if exchange1.account.in_position or exchange2.account.in_position:
                    continue
                result = self.entry_condition(*data)
                if result:
                    result = [pair, *result]
                    with self.lock:
                        del self.neutral_pairs[key]
                        self.ordered_pairs.add(*result)

    def entry_order_check_execution(self):
        """
        Execute the ordercheck condition for all pairs
        """
        while True:
            with self.lock:
                exchange_pairs = self.entry_orders.copy()
            for key, data in exchange_pairs.items():
                pair, buy_order_exchange, sell_order_exchange, buy_order_id, sell_order_id = data
                result = self.entry_order_check_condition(*data)
                if result:
                    if result[0] == "filled":
                        result = [pair, result[1], result[3]]
                        with self.lock:
                            del self.entry_orders[key]
                            self.positions.add(*result)
                    elif result[0] == "cancelled":
                        result = [pair, result[1], result[2]]
                        with self.lock:
                            del self.entry_orders[key]
                            self.neutral_pairs.add(*result)
            time.sleep(1)

    def exit_cond_execution(self):
        """
        Execute the exit condition for all pairs
        """
        while True:
            with self.lock:
                exchange_pairs = self.positions.copy()
            for key, data in exchange_pairs.items():
                pair, buy_exchange, sell_exchange = data
                result = self.exit_condition(*data)
                if result:
                    result = [pair, *result]
                    with self.lock:
                        del self.positions[key]
                        self.exit_orders.add(*result)
            time.sleep(1)

    def exit_order_check_execution(self):
        """
        Execute the ordercheck condition for all pairs
        """
        while True:
            with self.lock:
                exchange_pairs = self.exit_orders.copy()
            for key, data in exchange_pairs.items():
                pair, buy_order_exchange, sell_order_exchange, buy_order_id, sell_order_id = data
                result = self.exit_order_check_condition(*data)
                if result:
                    if result[0] == "filled":
                        with self.lock:
                            del self.exit_orders[key]
                            self._add_successful_position(result[2], result[4])
                            self.neutral_pairs.add(
                                pair, buy_order_exchange, sell_order_exchange)
                    elif result[0] == "cancelled":
                        result = [pair, result[1], result[2]]
                        with self.lock:
                            del self.exit_orders[key]
                            self.positions.add(
                                pair, buy_order_exchange, sell_order_exchange)
            time.sleep(1)

    def _add_successful_position(self, buy_position, sell_position):
        """
        Add a successful position to the positions list
        """
        pass
        # self._closed_positions.add(buy_position, sell_position)

    @staticmethod
    def _hash(exchange1, exchange2, pair):
        return exchange1.name + exchange2.name + str(pair)

    def start(self, wait_time=15):
        if self._running:
            print('Strategy already running!!!')
            return
        self._start_exchanges()
        self._running = True
        print(f'Sleep for {wait_time} seconds...')
        time.sleep(wait_time)
        print('\nStarting strategy...')
        entry_thread = threading.Thread(target=self.entry_cond_execution)
        entry_order_thread = threading.Thread(
            target=self.entry_order_check_execution)
        exit_thread = threading.Thread(target=self.exit_cond_execution)
        exit_order_thread = threading.Thread(
            target=self.exit_order_check_execution)
        self.threads = [entry_thread, entry_order_thread,
                        exit_thread, exit_order_thread]
        for thrd in self.threads:
            thrd.start()

    def _start_exchanges(self):
        print('Waiting for exchanges sockets to start...')
        for exchange in self.exchanges:
            exchange.start()

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
        result['number_of_winning_trades'] = len(
            [position for position in closed_positions if position.profit_amount > 0])
        result['number_of_losing_trades'] = len(
            [position for position in closed_positions if position.profit_amount < 0])
        result['profit_amount'] = sum(
            [position.profit_amount for position in closed_positions])
        result['profit_percentage'] = result['profit_amount'] / \
            sum([exchange.account._start_cash for exchange in self.exchanges]) * 100
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

    # def condition_thread(self, exchange1, exchange2, pairs):
    #     while True:
    #         for pair in pairs:

    #             key = ArbitrageStrategy._hash(exchange1, exchange2, pair)
    #             positionpair = self._open_positions.get(key, None)
    #             if positionpair:
    #                 result = self.exit_condition(positionpair.buy_exchange, positionpair.sell_exchange, pair)
    #                 if result:
    #                     positionpair.calc_profit()
    #                     self._closed_positions.append(positionpair)
    #                     del self._open_positions[key]
    #             else:
    #                 if exchange1.account.in_position or exchange2.account.in_position:
    #                     continue
    #                 result = self.entry_condition(exchange1, exchange2, pair)
    #                 if result:
    #                     self._open_positions[key] = PositionPair(*result)
    #         time.sleep(1)
