import string
#import sys; sys.setrecursionlimit(10 ** 5)


_isChar = lambda s: isinstance(s, str) and len(s) == 1
_DEBUG = False
_dbgCategories = {"general": True, "match": True, "matchres": True}
dbg = lambda *args, **kwargs: print(f"[DBG:{args[0]}]", *args[1:], **kwargs) if _DEBUG and _dbgCategories.get(args[0], True) else None


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
    def __init__(self, left, right):
        assert isinstance(left, Match) and isinstance(right, Match)
        self.left = left
        self.right = right
        dbg("matchres", self)
    
    def __str__(self):
        return str(self.left) + str(self.right)


def DisjunctionMatch(Match):
    def __init__(self, inner, id):
        assert isinstance(inner, Match) and isinstance(id, int)
        self.inner = inner
        self.id = id
        dbg("matchres", self)
    
    def __str__(self):
        return str(self.inner)


class RepetitionMatch(Match):
    def __init__(self, inners):
        assert all([isinstance(e, Match) for e in inners])
        self.inners = inners
        dbg("matchres", self)
    
    def __str__(self):
        return "".join([str(e) for e in self.inners if e])


class ElementMatch(Match):
    def __init__(self, inner, name="unnamed", handler=lambda self: None):
        assert isinstance(inner, Match)
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
            return ConcatenationDef(self, other)
        return NotImplemented
    
    def __radd__(self, other):
        other = self._convert(other)
        if isinstance(other, Definition):
            return ConcatenationDef(other, self)
        return NotImplemented
    
    def __or__(self, other):
        other = self._convert(other)
        if isinstance(other, Definition):
            return DisjunctionDef(self, other)
        return NotImplemented
    
    def __ror__(self, other):
        other = self._convert(other)
        if isinstance(other, Definition):
            return DisjunctionDef(other, self)
        return NotImplemented


class StringDef(Definition):
    def __init__(self, value):
        assert isinstance(value, str)
        self.value = value
    
    def check(self, buf, index):
        return super().check(buf, index) and buf[index:index + len(self.value)] == self.value
    
    def match(self, buf, index):
        dbg("match", "strg", index, self)
        assert self.check(buf, index)
        return StringMatch(self.value), index + len(self.value)
    
    def __str__(self):
        return repr(self.value)


class CharRangeDef(Definition):
    def __init__(self, left, right):
        assert _isChar(left) and _isChar(right)
        self.left = left
        self.right = right
    
    def check(self, buf, index):
        return super().check(buf, index) and self.left <= buf[index] <= self.right
    
    def match(self, buf, index):
        dbg("match", "chrr", index, self)
        assert self.check(buf, index)
        return StringMatch(buf[index]), index + 1
    
    def __str__(self):
        return f"[{repr(self.left)}..{repr(self.right)}]"


class CharSetDef(Definition):
    def __init__(self, value):
        value = set(value)
        assert all([_isChar(e) for e in value])
        self.value = value
    
    def check(self, buf, index):
        return super().check(buf, index) and buf[index] in self.value
    
    def match(self, buf, index):
        dbg("match", "chrs", index, self)
        assert self.check(buf, index)
        return StringMatch(buf[index]), index + 1
    
    def __str__(self):
        return repr(self.value)


class ConcatenationDef(Definition):
    def __init__(self, left, right):
        assert isinstance(left, Definition) and isinstance(right, Definition)
        self.left = left
        self.right = right
    
    def check(self, buf, index):
        try:
            self.match(buf, index)
            return True
        except AssertionError:
            return False
    
    def match(self, buf, index):
        dbg("match", "conc", index, self)
        left, index = self.left.match(buf, index)
        right, index = self.right.match(buf, index)
        return ConcatenationMatch(left, right), index
    
    def __str__(self):
        left = str(self.left)
        if isinstance(self.left, DisjunctionDef):
            left = f"({left})"
        right = str(self.right)
        if isinstance(self.right, DisjunctionDef):
            right = f"({right})"
        return f"{left} + {right}"


class DisjunctionDef(Definition):
    def __init__(self, left, right):
        assert isinstance(left, Definition) and isinstance(right, Definition)
        self.left = left
        self.right = right
    
    def check(self, buf, index):
        return self.left.check(buf, index) or self.right.check(buf, index)
    
    def match(self, buf, index):
        dbg("match", "disj", index, self)
        try:
            return DisjunctionMatch(self.left.match(buf, index), 0)
        except AssertionError:
            return DisjunctionMatch(self.right.match(buf, index), 1)
    
    def __str__(self):
        return f"{self.left} | {self.right}"


class RepetitionDef(Definition):
    def __init__(self, inner, range):
        assert isinstance(inner, Definition)
        self.inner = inner
        if isinstance(range, int):
            range = (range, range + 1)
        assert isinstance(range, tuple) and len(range) == 2 \
                                   and 0 <= range[0] and -1 <= range[1]
        self.range = range
    
    def check(self, buf, index):
        try:
            self.match(buf, index)
            return True
        except AssertionError:
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
            except AssertionError:
                break
        return RepetitionMatch(inners), index
    
    def __str__(self):
        inner = str(self.inner)
        if isinstance(self.inner, (DisjunctionDef, ConcatenationDef, RepetitionDef)):
            inner = f"({inner})"
        return f"{inner} * {self.range}"


class ElementDef(Definition):
    def __init__(self, name="unnamed", handler=lambda self: None):
        self.name = name
        self.definition = None
        self.handler = handler
    
    def define(self, definition):
        assert isinstance(definition, Definition)
        self.definition = definition
    
    def isDefined(self):
        return self.definition is not None
    
    def check(self, buf, index):
        return self.isDefined() and super().check(buf, index) and self.definition.check(buf, index)
    
    def match(self, buf, index):
        dbg("match", "elem", index, self)
        assert self.isDefined()
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
    integer = str(self.inner.left)
    fractional = str(self.inner.right)
    res = int(integer)
    if fractional:
        res += float("0" + fractional)
    return res

def factorHandler(self):
    if isinstance(self.inner, ConcatenationMatch):
        if isinstance(self.inner.right, StringMatch) and self.inner.right.evaluate() == ")":
            return self.inner.left.right.customEvaluate()
        return -self.inner.right.customEvaluate()
    return self.inner.customEvaluate()

def termHandler(self):
    res = self.inner.left.customEvaluate()
    for factor in self.inner.right.inners:
        op, factor = factor.left.evaluate(), factor.right.customEvaluate()
        res = operatorLookup[op](res, factor)
    return res

def exprHandler(self):
    res = self.inner.left.customEvaluate()
    for term in self.inner.right.inners:
        op, term = term.left.evaluate(), term.right.customEvaluate()
        res = operatorLookup[op](res, term)
    return res


expr = ElementDef("expr", exprHandler)
term = ElementDef("term", termHandler)
factor = ElementDef("factor", factorHandler)
number = ElementDef("number", numberHandler)
#whitespace = ElementDef("whitespace")
expr.define(term + (CharSetDef("+-") + term) * (0, -1))
term.define(factor + (CharSetDef("*/") + factor) * (0, -1))
factor.define(number | "(" + expr + ")" | "-" + factor)
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