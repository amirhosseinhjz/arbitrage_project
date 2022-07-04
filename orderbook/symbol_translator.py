import json
import os

class SymbolTranslator:
    def __init__(self):
        self.path = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')

    def get_exchange_data(self, exchange):
        exchange_name = exchange.exchange
        market_type = exchange.market_type
        if not hasattr(self, f'{exchange_name}_{market_type}'):
            exchange_data = json.load(
                open(self.path+f'/exchange/symbols/{exchange_name}_{market_type}.json'))
            setattr(self, f'{exchange_name}_{market_type}', exchange_data)
        return getattr(self, f'{exchange_name}_{market_type}')

    def __call__(self, exchange, asset1, asset2):
        exchange_data = self.get_exchange_data(exchange)
        return self.get_symbol(exchange_data, asset1, asset2)

    def has_pair(self, exchange, asset1, asset2):
        exchange_data = self.get_exchange_data(exchange)
        return self.has_pair_in_exchange_data(exchange_data, asset1, asset2)
    
    def has_pair_in_exchange_data(self, exchange_data, asset1, asset2):
        if asset1 in exchange_data:
            if asset2 in exchange_data[asset1]:
                return True
        if asset2 in exchange_data:
            if asset1 in exchange_data[asset2]:
                return True
        return False

    @staticmethod
    def get_symbol(exchange_data, asset1, asset2):
        asset1 = asset1.upper()
        asset2 = asset2.upper()
        try:
            return exchange_data[asset1][asset2]
        except KeyError:
            try:
                return exchange_data[asset2][asset1]
            except KeyError:
                raise Exception(f'No symbol found for pair {asset1}-{asset2}')


symboltranslator = SymbolTranslator()
