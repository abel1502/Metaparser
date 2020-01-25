import string
#import sys; sys.setrecursionlimit(10 ** 5)


_isChar = lambda s: isinstance(s, str) and len(s) == 1
_DEBUG = False
_dbgCategories = {"general": True, "match": True, "matchres": True, "error": True}
dbg = lambda *args, **kwargs: print(f"[DBG:{args[0]}]", *args[1:], **kwargs) if _DEBUG and _dbgCategories.get(args[0], True) else None


class ParserError(Exception):
    pass


class MatchError(ParserError):
    pass


class UndefinedElementError(ParserError):
    pass


class Match:
    pass


class StringMatch(Match):
    def __init__(self, value):
        assert isinstance(value, str)
        self.value = value
        dbg("matchres", self)
    
    def __str__(self):
        return self.value


class ConcatenationMatch(Match):
    def __init__(self, inners):
        if not all([isinstance(e, Match) for e in inners]):
            raise ValueError("All inner values must be instances of Match")
        self.inners = inners
        dbg("matchres", self)
    
    def __str__(self):
        return "".join([str(e) for e in self.inners if e])


class DisjunctionMatch(Match):
    def __init__(self, inner, id):
        if not (isinstance(inner, Match) and isinstance(id, int)):
            dbg("error", inner, id)
            raise ValueError("Inner value must be an instance of Match, id must be int")
        self.inner = inner
        self.id = id
        dbg("matchres", self)
    
    def __str__(self):
        return str(self.inner)


class ElementMatch(Match):
    def __init__(self, inner, name="unnamed", handler=lambda self: None):
        if not isinstance(inner, Match):
            raise ValueError("Inner value must be an instance of Match")
        self.inner = inner
        self.name = name
        self.handler = handler
        dbg("matchres", self)
    
    def evaluate(self):
        return self.handler(self)
    
    def __str__(self):
        return str(self.inner)


class Definition:
    def check(self, buf, index):
        return 0 <= index < len(buf)
    
    def match(self, buf, index):
        raise NotImplementedError()
    
    @staticmethod
    def _convert(value):
        if isinstance(value, str):
            value = StringDef(value)
        if isinstance(value, (tuple, list)) and len(value) == 2:
            value = CharRangeDef(*value)
        return value
    
    def __mul__(self, other):
        if isinstance(other, tuple) and len(other) == 2:
            return RepetitionDef(self, other)
        return NotImplemented
    
    def __rmul__(self, other):
        if isinstance(other, tuple) and len(other) == 2:
            return RepetitionDef(self, other)
        return NotImplemented
    
    def __add__(self, other):
        other = self._convert(other)
        if isinstance(other, Definition):
            return ConcatenationDef([self, other])
        return NotImplemented
    
    def __radd__(self, other):
        other = self._convert(other)
        if isinstance(other, Definition):
            return ConcatenationDef([other, self])
        return NotImplemented
    
    def __or__(self, other):
        other = self._convert(other)
        if isinstance(other, Definition):
            return DisjunctionDef([self, other])
        return NotImplemented
    
    def __ror__(self, other):
        other = self._convert(other)
        if isinstance(other, Definition):
            return DisjunctionDef([other, self])
        return NotImplemented


class StringDef(Definition):
    def __init__(self, value):
        if not isinstance(value, str):
            raise ValueError("Value must be str")
        self.value = value
    
    def check(self, buf, index):
        return super().check(buf, index) and buf[index:index + len(self.value)] == self.value
    
    def match(self, buf, index):
        dbg("match", "strg", index, self)
        if not self.check(buf, index):
            raise MatchError()
        return StringMatch(self.value), index + len(self.value)
    
    def __str__(self):
        return repr(self.value)


class CharRangeDef(Definition):
    def __init__(self, left, right):
        if not (_isChar(left) and _isChar(right)):
            raise ValueError("Borders must be 1-long strings")
        self.left = left
        self.right = right
    
    def check(self, buf, index):
        return super().check(buf, index) and self.left <= buf[index] <= self.right
    
    def match(self, buf, index):
        dbg("match", "chrr", index, self)
        if not self.check(buf, index):
            raise MatchError()
        return StringMatch(buf[index]), index + 1
    
    def __str__(self):
        return f"[{repr(self.left)}..{repr(self.right)}]"


class CharSetDef(Definition):
    def __init__(self, value):
        value = set(value)
        if not all([_isChar(e) for e in value]):
            raise ValueError("Value must be a set of 1-long strings")
        self.value = value
    
    def check(self, buf, index):
        return super().check(buf, index) and buf[index] in self.value
    
    def match(self, buf, index):
        dbg("match", "chrs", index, self)
        if not self.check(buf, index):
            raise MatchError()
        return StringMatch(buf[index]), index + 1
    
    def __str__(self):
        return repr(self.value)


class ConcatenationDef(Definition):
    def __init__(self, inners):
        if not all([isinstance(e, Definition) for e in inners]):
            raise ValueError("All inner values must be instances of Definition")
        self.inners = inners
    
    def check(self, buf, index):
        try:
            self.match(buf, index)
            return True
        except MatchError:
            return False
    
    def match(self, buf, index):
        dbg("match", "conc", index, self)
        innerMatches = []
        for innerDef in self.inners:
            innerMatch, index = innerDef.match(buf, index)
            innerMatches.append(innerMatch)
        return ConcatenationMatch(innerMatches), index
    
    def __str__(self):
        return "(" + " + ".join(map(str, self.inners)) + ")"


class DisjunctionDef(Definition):
    def __init__(self, inners):
        if not all([isinstance(e, Definition) for e in inners]):
            raise ValueError("All inner values must be instances of Definition")
        self.inners = inners
    
    def check(self, buf, index):
        return any([e.check(buf, index) for e in self.inners])
    
    def match(self, buf, index):
        dbg("match", "disj", index, self)
        for i, inner in enumerate(self.inners):
            try:
                innerMatch, index = inner.match(buf, index)
                return DisjunctionMatch(innerMatch, i), index
            except MatchError:
                pass
        raise MatchError()
    
    def __str__(self):
        return "(" + " | ".join(map(str, self.inners)) + ")"


class RepetitionDef(Definition):
    def __init__(self, inner, range):
        if not isinstance(inner, Definition):
            raise ValueError("Inner value must be an instance of Definition")
        self.inner = inner
        if isinstance(range, int):
            range = (range, range + 1)
        if not (isinstance(range, tuple) and len(range) == 2 \
                    and 0 <= range[0] and -1 <= range[1]):
            raise ValueError("Repetition count must be int or tuple of two ints")
        self.range = range
    
    def check(self, buf, index):
        try:
            self.match(buf, index)
            return True
        except MatchError:
            return False
    
    def match(self, buf, index):
        dbg("match", "rept", index, self)
        i = 0
        inners = []
        while i < self.range[0]:
            dbg("match", "rept_inner", i)
            inner, index = self.inner.match(buf, index)
            inners.append(inner)
            i += 1
        while self.range[1] == -1 or i < self.range[1]:
            dbg("match", "rept_inner", i)
            try:
                inner, index = self.inner.match(buf, index)
                inners.append(inner)
                i += 1
            except MatchError:
                break
        return ConcatenationMatch(inners), index
    
    def __str__(self):
        return f"{self.inner} * {self.range}"


class ElementDef(Definition):
    def __init__(self, name="unnamed", handler=lambda self: None):
        self.name = name
        self.definition = None
        self.handler = handler
    
    def define(self, definition):
        if not isinstance(definition, Definition):
            raise ValueError("Definition must be an instance of Definition")
        self.definition = definition
    
    def isDefined(self):
        return self.definition is not None
    
    def check(self, buf, index):
        return self.isDefined() and super().check(buf, index) and self.definition.check(buf, index)
    
    def match(self, buf, index):
        dbg("match", "elem", index, self)
        if not self.isDefined():
            raise UndefinedElementError()
        inner, index = self.definition.match(buf, index)
        return ElementMatch(inner, name=self.name, handler=self.handler), index
    
    def expand(self):
        return f"{self} ::= {self.definition}"
    
    def __str__(self):
        return f"<{self.name}>"


digits = CharRangeDef("0", "9")
alphaLower = CharRangeDef("a", "z")
alphaUpper = CharRangeDef("A", "Z")


#test = ElementDef("test")
#test.define(digits * (1, -1))
#toParse = "123"
#dbg("buf =", repr(toParse))
#match, index = test.match(toParse, 0)
#print(match, index)


import operator
operatorLookup = {"+": operator.add, "-": operator.sub, "/": operator.truediv, "*": operator.mul}


def numberHandler(self):
    integer = str(self.inner.inners[0])
    fractional = str(self.inner.inners[1])
    res = int(integer)
    if fractional:
        res += float("0" + fractional)
    return res

def factorHandler(self):
    variant = self.inner.id
    if variant == 0:
        return self.inner.inner.evaluate()
    elif variant == 1:
        return self.inner.inner.inners[0].inners[1].evaluate()
    elif variant == 2:
        return -self.inner.inner.inners[1].evaluate()

def termHandler(self):
    res = self.inner.inners[0].evaluate()
    for factor in self.inner.inners[1].inners:
        op, factor = str(factor.inners[0]), factor.inners[1].evaluate()
        res = operatorLookup[op](res, factor)
    return res

def exprHandler(self):
    res = self.inner.inners[0].evaluate()
    for term in self.inner.inners[1].inners:
        op, term = str(term.inners[0]), term.inners[1].evaluate()
        res = operatorLookup[op](res, term)
    return res


expr = ElementDef("expr", exprHandler)
term = ElementDef("term", termHandler)
factor = ElementDef("factor", factorHandler)
number = ElementDef("number", numberHandler)
#whitespace = ElementDef("whitespace")
expr.define(term + (CharSetDef("+-") + term) * (0, -1))
term.define(factor + (CharSetDef("*/") + factor) * (0, -1))
factor.define(DisjunctionDef([number, "(" + expr + ")", "-" + factor]))
number.define(digits * (1, -1) + ("." + digits * (0, -1)) * (0, 1))

print(expr.expand())
print(term.expand())
print(factor.expand())
print(number.expand())
#print(whitespace.expand())

toParse = "123+(17---456*-789)*5"
dbg("general", "buf =", repr(toParse))
match, index = expr.match(toParse, 0)
print()
print(match.evaluate())
print(eval(toParse))