def handle_expr(val):
    res = val.inners[0].evaluate()
    for e in val.inners[1].inners:
        op = str(e.inners[0])
        if op == "+":
            res += e.inners[1].evaluate()
        else:
            res -= e.inners[1].evaluate()
    return res

def handle_term(val):
    res = val.inners[0].evaluate()
    for e in val.inners[1].inners:
        op = str(e.inners[0])
        if op == "*":
            res *= e.inners[1].evaluate()
        else:
            res //= e.inners[1].evaluate()
    return res

def handle_factor(val):
    if val.id == 0:
        return val.inner.evaluate()
    if val.id == 1:
        return -val.inner.inners[1].evaluate()
    return val.inner.inners[1].evaluate()

def handle_number(val):
    return int(str(val))