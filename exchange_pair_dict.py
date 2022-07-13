

class ExchangePairDict(dict):

    def _hash(self, *args):
        return ''.join([str(arg) for arg in args])

    def add(self, *args):
        key = self._hash(*args)
        self[key] = args

    def get(self, *args, otherside=False):
        key = self._hash(*args)
        if not otherside:
            return self[key]
        if key in self:
            return self[key]
        args[0], args[1] = args[1], args[0]
        key = self._hash(*args)
        return self[key]
