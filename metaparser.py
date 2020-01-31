import string
import importlib.util
import os, pathlib
#import sys; sys.setrecursionlimit(10 ** 5)


_isChar = lambda s: isinstance(s, str) and len(s) == 1
_DEBUG = False
_dbgCategories = {"general": True, "match": False, "matchres": False, "error": True, "mptest": True, "ctrl": True}
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
    def __init__(self, inner, name="unnamed", handler=lambda inner: None):
        if not isinstance(inner, Match):
            raise ValueError("Inner value must be an instance of Match")
        self.inner = inner
        self.name = name
        self.handler = handler
        dbg("matchres", self)
    
    def evaluate(self):
        return self.handler(self.inner)
    
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
        if isinstance(other, int):
            other = (other, other)
        if isinstance(other, tuple) and len(other) == 2:
            return RepetitionDef(self, other)
        return NotImplemented
    
    def __rmul__(self, other):
        if isinstance(other, int):
            other = (other, other)
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
    def __init__(self, left, right, inverted=False):
        if not (_isChar(left) and _isChar(right)):
            raise ValueError("Borders must be 1-long strings")
        self.left = left
        self.right = right
        self.inverted = inverted
    
    def check(self, buf, index):
        return super().check(buf, index) and ((self.left <= buf[index] <= self.right) ^ self.inverted)
    
    def match(self, buf, index):
        dbg("match", "chrr", index, self)
        if not self.check(buf, index):
            raise MatchError()
        return StringMatch(buf[index]), index + 1
    
    def __invert__(self):
        return CharRangeDef(self.left, self.right, inverted=(not self.inverted))
    
    def __str__(self):
        return f"[{repr(self.left)}..{repr(self.right)}]"


class CharSetDef(Definition):
    def __init__(self, value, inverted=False):
        value = set(value)
        if not all([_isChar(e) for e in value]):
            raise ValueError("Value must be a set of 1-long strings")
        self.value = value
        self.inverted = inverted
    
    def check(self, buf, index):
        return super().check(buf, index) and ((buf[index] in self.value) ^ self.inverted)
    
    def match(self, buf, index):
        dbg("match", "chrs", index, self)
        if not self.check(buf, index):
            raise MatchError()
        return StringMatch(buf[index]), index + 1
    
    def __invert__(self):
        return CharSetDef(self.value, inverted=(not self.inverted))
    
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
    def __init__(self, name="unnamed", handler=lambda inner: None):
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
hexdigits = CharSetDef("0123456789abcdef")
alphaLower = CharRangeDef("a", "z")
alphaUpper = CharRangeDef("A", "Z")
alpha = alphaLower | alphaUpper


class AbstractParser:
    bufferType = str
    mainElement = None
    defined = False
    
    def __init__(self):
        if not self.defined:
            self.mainElement = self.define()
            self.defined = True
        self.clear()
    
    @classmethod
    def define(cls):
        pass
    
    def feed(self, data):
        self.buf += data
    
    def clear(self):
        self.buf = self.bufferType()
    
    def parse(self):
        assert self.defined
        match, index = self.mainElement.match(self.buf, 0)
        dbg("general", match, index)
        assert index == len(self.buf)
        return match.evaluate()


class MetaParserHandlers:
    def __init__(self):
        self.elements = {}
        self.handlers = None
        self.metadata = {"name": None, "main": None}
    
    def handle_defs(self, val):
        for ctrl in val.inners[0].inners:
            if ctrl.id == 0:
                ctrl.inner.evaluate()
        for line in val.inners[1].inners:
            line.inners[0].inner.evaluate()
        if self.handlers is not None:
            for name in self.elements:
                elem = self.elements[name]
                if hasattr(self.handlers, f"handle_{name}"):
                    elem.handler = getattr(self.handlers, f"handle_{name}")
        if self.metadata["name"] is None:
            self.metadata["name"] = "CustomParser"
        parser = type(self.metadata["name"], (AbstractParser,), {"mainElement": self.elements[self.metadata["main"]], "defined": True})
        return parser
    
    def handle_defn(self, val):
        self.elements[val.inners[0].evaluate()].define(val.inners[2].evaluate())
    
    def handle_disj(self, val):
        concs = [val.inners[0].evaluate()]
        for e in val.inners[1].inners:
            concs.append(e.inners[1].evaluate())
        if len(concs) == 1:
            return concs[0]
        return DisjunctionDef(concs)
    
    def handle_conc(self, val):
        repts = [val.inners[0].evaluate()]
        for e in val.inners[1].inners:
            repts.append(e.inners[1].evaluate())
        if len(repts) == 1:
            return repts[0]
        return ConcatenationDef(repts)
    
    def handle_rept(self, val):
        res = val.inners[0].evaluate()
        if len(val.inners[1].inners) == 1:
            res *= val.inners[1].inners[0].inners[1].inner.evaluate()
        return res
    
    def handle_range(self, val):
        start = val.inners[2].evaluate()
        end = val.inners[4]
        if end.id == 0:
            end = end.inner.evaluate()
        else:
            end = -1
        return (start, end)
    
    def handle_simple(self, val):
        if val.id == 0:
            return StringDef(val.inner.evaluate())
        if val.id == 3:
            return self.elements[val.inner.evaluate()]
        if val.id == 4:
            return val.inner.inners[2].evaluate()
        return val.inner.evaluate()
    
    def handle_intg(self, val):
        return int(str(val.inners[1]))
    
    def handle_strg(self, val):
        val = val.inners[1].inner.inners[1]
        return ''.join([e.evaluate() for e in val.inners])
    
    def handle_char(self, val):
        return val.inners[1].inner.inners[1].evaluate()
    
    def handle_chrs(self, val):
        return CharSetDef(val.inners[2].evaluate())
    
    def handle_chrr(self, val):
        return CharRangeDef(val.inners[2].evaluate(), val.inners[4].evaluate())
    
    def handle_elem(self, val):
        elemName = str(val.inners[1])
        if elemName not in self.elements:
            self.elements[elemName] = ElementDef(elemName)
        if self.metadata["main"] is None:
            self.metadata["main"] = elemName
        return elemName
    
    def handle_ctrl(self, val):
        val.inners[2].evaluate()
    
    def handle_mdata(self, val):
        cmd = str(val.inner.inners[0])
        args = val.inner.inners[2]
        dbg("ctrl", cmd, args)
        if cmd == "name":
            assert self.metadata["name"] is None
            self.metadata["name"] = args.evaluate()
        elif cmd == "main":
            assert self.metadata["main"] is None
            args.evaluate()  # Writes itself to main automatically
    
    def handle_qchar(self, val):
        if val.id == 0:
            return str(val.inner)
        return val.inner.evaluate()
    
    def handle_eseq(self, val):
        return bytes(str(val), "utf-8").decode("unicode_escape")


class MetaParser(AbstractParser):
    def feed(self, data, handlers=None, handlersClass=None):
        super().feed(data)
        if handlers is not None:
            spec = importlib.util.spec_from_file_location("module.name", handlers)
            handlers = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(handlers)
            if handlersClass is not None:
                handlers = getattr(handlers, handlersClass)()
            self._handlers.handlers = handlers
            
    
    @classmethod
    def define(cls):
        handlers = MetaParserHandlers()
        cls._handlers = handlers
        
        defs = ElementDef("defs", handlers.handle_defs)
        defn = ElementDef("defn", handlers.handle_defn)
        disj = ElementDef("disj", handlers.handle_disj)
        conc = ElementDef("conc", handlers.handle_conc)
        rept = ElementDef("rept", handlers.handle_rept)
        range = ElementDef("range", handlers.handle_range)
        simple = ElementDef("simple", handlers.handle_simple)
        intg = ElementDef("intg", handlers.handle_intg)
        strg = ElementDef("strg", handlers.handle_strg)
        char = ElementDef("char", handlers.handle_char)
        chrs = ElementDef("chrs", handlers.handle_chrs)
        chrr = ElementDef("chrr", handlers.handle_chrr)
        elem = ElementDef("elem", handlers.handle_elem)
        cmnt = ElementDef("cmnt")
        ctrl = ElementDef("ctrl", handlers.handle_ctrl)
        mdata = ElementDef("mdata", handlers.handle_mdata)
        dqchr = ElementDef("dqchar", handlers.handle_qchar)
        sqchr = ElementDef("sqchar", handlers.handle_qchar)
        eseq = ElementDef("eseq", handlers.handle_eseq)
        blank = ElementDef("blank")
        space = ElementDef("space")
        
        blank.define(CharSetDef(" \t") * (0, -1))
        space.define(CharSetDef(" \t") * (1, -1))
        defs.define((ctrl | cmnt) * (0, -1) + ((defn | blank) + (cmnt | "\n")) * (0, -1))
        defn.define(ConcatenationDef([elem, StringDef("::="), disj]))
        disj.define(conc + ("|" + conc) * (0, -1))
        conc.define(rept + ("+" + rept) * (0, -1))
        rept.define(simple + ("*" + (intg | range)) * (0, 1))
        range.define(ConcatenationDef([blank, StringDef("("), intg, StringDef(","), (intg | ConcatenationDef([blank, StringDef("inf"), blank])), StringDef(")"), blank]))
        simple.define(DisjunctionDef([strg, chrs, chrr, elem, ConcatenationDef([blank, StringDef("("), disj, StringDef(")"), blank])]))
        cmnt.define(ConcatenationDef([blank, StringDef("#"), (~CharSetDef("\n")) * (0, -1), StringDef("\n")]))
        ctrl.define(ConcatenationDef([blank, StringDef("#:"), mdata, StringDef("\n")]))
        _ctrlComments = (("name", strg), 
                                         ("main", elem)
                                         # Todo: use; ...
                                         )
        mdata.define(DisjunctionDef([ConcatenationDef([StringDef(name), space, args]) for name, args in _ctrlComments]))
        strg.define(ConcatenationDef([blank, ConcatenationDef([StringDef("\""), dqchr * (0, -1), StringDef("\"")]) | ConcatenationDef([StringDef("'"), sqchr * (0, -1), StringDef("'")]), blank]))
        char.define(ConcatenationDef([blank, ConcatenationDef([StringDef("\""), dqchr, StringDef("\"")]) | ConcatenationDef([StringDef("'"), sqchr, StringDef("'")]), blank]))
        intg.define(ConcatenationDef([blank, digits * (1, -1), blank]))
        chrr.define(ConcatenationDef([blank, StringDef("["), char, StringDef("-"), char, StringDef("]"), blank]))
        chrs.define(ConcatenationDef([blank, StringDef("{"), strg, StringDef("}"), blank]))
        elem.define(ConcatenationDef([blank, (alpha | "_") + DisjunctionDef([alpha, digits, StringDef("_")])* (0, -1), blank]))
        dqchr.define((~CharSetDef("\\\"\n")) | eseq)
        sqchr.define((~CharSetDef("\\\'\n")) | eseq)
        eseq.define("\\" + (CharSetDef("\\\"'rnt") | "x" + hexdigits * 2 | "u" + hexdigits * 4))
        
        return defs


targetFile = "./test/math.bbnf"
targetHandlers = "./test/math.py"
targetClass = None

mp = MetaParser()
mp.feed(open(targetFile, "r").read(), handlers=targetHandlers, handlersClass=targetClass)
Parser = mp.parse()
p = Parser()
p.feed("1+2*(3-14)--17")
print(p.parse())




#import operator
#operatorLookup = {"+": operator.add, "-": operator.sub, "/": operator.truediv, "*": operator.mul}

#def numberHandler(self):
#    integer = str(self.inner.inners[0])
#    fractional = str(self.inner.inners[1])
#    res = int(integer)
#    if fractional:
#        res += float("0" + fractional)
#    return res

#def factorHandler(self):
#    variant = self.inner.id
#    if variant == 0:
#        return self.inner.inner.evaluate()
#    elif variant == 1:
#        return self.inner.inner.inners[0].inners[1].evaluate()
#    elif variant == 2:
#        return -self.inner.inner.inners[1].evaluate()

#def termHandler(self):
#    res = self.inner.inners[0].evaluate()
#    for factor in self.inner.inners[1].inners:
#        op, factor = str(factor.inners[0]), factor.inners[1].evaluate()
#        res = operatorLookup[op](res, factor)
#    return res

#def exprHandler(self):
#    res = self.inner.inners[0].evaluate()
#    for term in self.inner.inners[1].inners:
#        op, term = str(term.inners[0]), term.inners[1].evaluate()
#        res = operatorLookup[op](res, term)
#    return res


#class MathExprParser(AbstractParser):
#    @classmethod
#    def define(cls):
#        expr = ElementDef("expr", exprHandler)
#        term = ElementDef("term", termHandler)
#        factor = ElementDef("factor", factorHandler)
#        number = ElementDef("number", numberHandler)
#        #whitespace = ElementDef("whitespace")
#        expr.define(term + (CharSetDef("+-") + term) * (0, -1))
#        term.define(factor + (CharSetDef("*/") + factor) * (0, -1))
#        factor.define(DisjunctionDef([number, "(" + expr + ")", "-" + factor]))
#        number.define(digits * (1, -1) + ("." + digits * (0, -1)) * (0, 1))
#        return expr

#print(expr.expand())
#print(term.expand())
#print(factor.expand())
#print(number.expand())
#print(whitespace.expand())

#toParse = "123+(17---456*-789)*5"
#dbg("general", "buf =", repr(toParse))
#mep = MathExprParser(toParse)
#print(mep.parse())
#print(eval(toParse))