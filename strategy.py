from . import orderbook
import threading
import time
import abc
import time
from itertools import combinations, permutations

from .orderbook.symbol_translator import symboltranslator






class ArbitrageStrategy:

    @abc.abstractmethod
    def __init__(self, pairs):
        self.pairs = pairs
        self.exchanges = []

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
    def condition(self, exchange1, exchange2, pair):
        """"
        write this function to implement your arbitrage strategy
        """
        pass

    @staticmethod
    def calc_permutations(exchanges):
        exchange_combinations = list(combinations(exchanges, 2))
        return exchange_combinations

    def start(self):
        print('Waiting for exchanges sockets to start...')
        for exchange in self.exchanges:
            exchange.start()
        print('Sleep for 30 seconds...')
        time.sleep(30)
        self.threads = []
        exchange_pair_permutations = self.calc_permutations(self.exchanges)
        print('\nStarting strategy...')
        for exchange1, exchange2 in exchange_pair_permutations:
            thread = threading.Thread(target=self.condition_thread, args=(exchange1, exchange2, self.pairs))
            thread.start()
            self.threads.append(thread)

    def condition_thread(self, exchange1, exchange2, pairs):
        while True:
            for pair in pairs:
                self.conditions(exchange1, exchange2, pair)
            time.sleep(1)