import json
import os

class SymbolTranslator:
    def __init__(self):
        self.path = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')

    def __call__(self, exchange, asset1, asset2, market_type):
        if not hasattr(self, f'{exchange}_{market_type}'):
            exchange_data = json.load(
                open(self.path+f'/exchange_data/{exchange}_{market_type}.json'))
            setattr(self, f'{exchange}_{market_type}', exchange_data)
        exchange_data = getattr(self, f'{exchange}_{market_type}')
        return self.get_symbol(exchange_data, asset1, asset2)

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
