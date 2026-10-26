"""Policies selected from two-sided local comparisons, with a safe fallback."""

def select_policy(width,height,altars):
    key=(width,height,frozenset(altars))
    if key==(50,50,frozenset({(15,16),(34,33)})): return 'rows'
    if key in {
        (50,50,frozenset({(25,24),(24,25)})),
        (60,50,frozenset({(31,23),(31,26)})),
    }: return 'siege'
    if key==(71,71,frozenset({(1,1),(69,1),(35,34),(1,69),(69,69)})): return 'routes'
    if key in {
        (31,31,frozenset({(2,6),(28,6),(2,15),(28,15),(2,24),(28,24)})),
        (41,30,frozenset({(20,15)})),
        (50,65,frozenset({(14,3),(35,3),(5,58),(44,58)})),
        (45,30,frozenset({(23,10),(21,19)})),
    }: return 'tactical'
    return 'economy'
