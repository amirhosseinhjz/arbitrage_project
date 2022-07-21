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
import asyncio

class ArbitrageStrategy:

    @abc.abstractmethod
    def __init__(self, pairs):
        self._running = False
        self.pairs = pairs
        self.exchanges = []
        self._open_positions = {}
        self._closed_positions = []

    def _init_before_start(self):
        self.noposition_pairs = asyncio.Queue()
        self.entryorder_pairs = asyncio.Queue()
        self.openposition_pairs = asyncio.Queue()
        self.exitorder_pairs = asyncio.Queue()
        exchange_permutations = self.calc_permutations(self.exchanges)
        pairs = self.validate_pairs(self.exchanges, self.pairs)
        exchanges_pairs = list(itertools.chain(
            itertools.product(pairs, exchange_permutations)))
        # print(exchanges_pairs)
        asyncio.run(self._put_to_queue(self.noposition_pairs, exchanges_pairs))

    async def _put_to_queue(self, queue, exchanges_pairs):
        """
        Put args to queue
        """
        for pair, (exchange1, exchange2) in exchanges_pairs:
            await queue.put((pair, exchange1, exchange2))

    def validate_pairs(self, exchanges, pairs):
        """
        Remove pairs that are not supported by any of the exchanges
        """
        validated_pairs = []
        for pair in pairs:
            for exchange in exchanges:
                if not symboltranslator.has_pair(exchange, *pair):
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
            sell_exchange: exchange in which the short order is sent,
            buy_order_id: order id of the long position,
            sell_order_id: order id of the short position
            ]
        """
        return

    def entry_order_check_condition(self, positionpair: PositionPair):
        """
        write this function to manage orders to be filled or killed
        if no change made, nothing should be returned
        if orders are done and position is started, return "filled"
        if orders are cancelled and position is started, return "cancelled"
        """
        return

    @abc.abstractmethod
    def exit_condition(self, positionpair: PositionPair):
        """
        write this function to implement your arbitrage strategy
        if no position closed nothing should be returned,
        if a position is closed the data below should be returned in the shown order:
            [
            long_position_exit_orderid: order id of the long close order,
            short_position_exit_orderid: order id of the short close order,
            ]
        """
        return

    @abc.abstractmethod
    def exit_order_check_condition(self, positionpair: PositionPair):
        """
        write this function to manage orders to be filled or killed
        if no change made, nothing should be returned
        if orders are done and position is closed successfully, return "filled"
        if orders are cancelled and position is closed successfully, return "cancelled"
        """
        return

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
        exchange1_max_qty = exchange1._cash / avg_price1
        exchange2_max_qty = exchange2._cash / avg_price2
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

    async def entry_cond_execution(self):
        """
        Execute the entry condition for all pairs
        """
        while True:
            noposition_pair = await self.noposition_pairs.get()
            pair = noposition_pair[0]
            result = self.entry_condition(*noposition_pair)
            if result:
                result = [pair] + list(result)
                buy_exchange, sell_exchange, buy_order_id, sell_order_id = result
                buy_order = buy_exchange.get_order(buy_order_id)
                sell_order = sell_exchange.get_order(sell_order_id)
                positionpair = PositionPair(pair, buy_exchange,
                        sell_exchange, buy_order, sell_order)
                await self.entryorder_pairs.put(positionpair)
            else:
                await self.noposition_pairs.put(noposition_pair)
            self.noposition_pairs.task_done()

    async def entry_order_check_execution(self):
        """
        Execute the ordercheck condition for all pairs
        """
        while True:
            positionpair = await self.entryorder_pairs.get()
            print("Entry order check:", positionpair)
            pair = positionpair.pair
            result = self.entry_order_check_condition(positionpair)
            if not result:
                await self.entryorder_pairs.put(positionpair)
                self.entryorder_pairs.task_done()
                continue
            # result_ = [pair] + result[1:3]
            if result == "filled":
                # TODO: save positionpair to database
                await self.openposition_pairs.put(positionpair)
            elif result[0] == "cancelled":
                # TODO: save cancelled positionpair to database
                await self.noposition_pairs.put((positionpair.pair, positionpair.buy_exchange, positionpair.sell_exchange))
            self.entryorder_pairs.task_done()

    async def exit_cond_execution(self):
        """
        Execute the exit condition for all pairs
        """
        while True:
            positionpair = await self.openposition_pairs.get()
            print("Exit cond:", positionpair)
            # pair = positionpair.pair
            result = self.exit_condition(positionpair)
            if result:
                long_close_order_id, short_close_order_id = result
                positionpair.long_position_exit_order = positionpair.long_exchange.get_order(long_close_order_id)
                positionpair.short_position_exit_order = positionpair.short_exchange.get_order(short_close_order_id)
                await self.exitorder_pairs.put(positionpair)
            else:
                await self.openposition_pairs.put(positionpair)
            self.openposition_pairs.task_done()

    async def exit_order_check_execution(self):
        """
        Execute the ordercheck condition for all pairs
        """
        while True:
            positionpair = await self.exitorder_pairs.get()
            print("Exit order check:", positionpair)
            result = self.exit_order_check_condition(positionpair)
            if not result:
                await self.exitorder_pairs.put(positionpair)
            elif result == "filled":
                # TODO: save positionpair to database
                await self.noposition_pairs.put((positionpair.pair, positionpair.buy_exchange, positionpair.sell_exchange))
            elif result == "cancelled":
                await self.openposition_pairs.put(positionpair)
            self.exitorder_pairs.task_done()

    def _add_successful_position(self, buy_position, sell_position):
        """
        Add a successful position to the positions list
        """
        pass
        # self._closed_positions.add(buy_position, sell_position)

    @staticmethod
    def _hash(exchange1, exchange2, pair):
        return exchange1.name + exchange2.name + str(pair)

    @staticmethod
    def get_valid_qty(exchange1, exchange2, pair, qty):
        """
        Validate the quantity between exchanges
        """
        exchange1_qty = exchange1.get_valid_qty(pair, qty)
        exchange2_qty = exchange2.get_valid_qty(pair, qty)
        qty = min(exchange1_qty, exchange2_qty)
        if exchange1.is_valid_qty(pair, qty) and exchange2.is_valid_qty(pair, qty):
            return qty
        return None

        

    async def _start_strategy(self):
        """
        Start the strategy
        """
        self._init_before_start()
        self.entry_condition_task = asyncio.ensure_future(self.entry_cond_execution())
        self.entry_order_check_task = asyncio.ensure_future(self.entry_order_check_execution())
        self.exit_condition_task = asyncio.ensure_future(self.exit_cond_execution())
        self.exit_order_check_task = asyncio.ensure_future(self.exit_order_check_execution())
        await asyncio.gather(self.entry_condition_task, self.entry_order_check_task, self.exit_condition_task,
                             self.exit_order_check_task)

    def start(self, wait_time=15):
        if self._running:
            print('Strategy already running!!!')
            return
        self._start_exchanges()
        self._running = True
        print(f'Sleep for {wait_time} seconds...')
        time.sleep(wait_time)
        print('\nStarting strategy...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._start_strategy())
        

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
