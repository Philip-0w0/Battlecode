"""Small static dispatch table; no live observation or SDK dependency."""
MODES={
    (100,80,frozenset({(76, 11), (23, 68), (41, 54), (58, 25)})):'TerritoryEconomy', # 02tangle
    (30,30,frozenset({(15, 24), (14, 5)})):'FragmentEconomy', # 00fragment
    (50,40,frozenset({(32, 20), (17, 19), (17, 20), (32, 19)})):'PreviousEconomy', # 00great-wall
    (40,40,frozenset({(19, 16), (20, 23), (36, 12), (3, 27)})):'PreviousTactical', # 00interlock
    (45,45,frozenset({(32, 24), (30, 16), (12, 20), (14, 28)})):'GiftEconomy', # 02gift-wrapping
    (51,51,frozenset({(25, 2), (25, 48), (25, 25)})):'CooperativeEconomy', # 02crossing
    (51,51,frozenset({(30, 25)})):'PreviousTactical', # adgato-gemcombat3
    (67,73,frozenset({(33, 36)})):'PreviousEconomy', # 03ultrastarvation
}
def choose_mode(signature):
    return MODES.get(signature)
