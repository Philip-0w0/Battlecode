# Starting strategy and development checkpoint

The active Python bot is bots/my-bot/src. Original starter-python remains unchanged; economy-v1 preserves the first improved version. No tournament submission has been made.

## Implemented opening
- Draft Varg, Vendetta and Tavi first on maps with grouped camps. On maps without grouped camps prefer Vendetta, Tavi and Vesper Vale. Larger teams add Vesper and Ryth.
- Spread champions among camps using shared-memory claims. Score camps by gems plus some gold value divided by estimated travel/clear time. Remember observed respawn timers. Avoid opening Monolith below 200 Strength.
- Use basic attacks and abilities; Varg benefits from splash on grouped targets. Tavi buys remotely. Vendetta's kill reset needs further testing: the engine sometimes rejects another reset despite the action-state check.
- Buy Jungle Strength first, then Monster Strength, Bruiser Health, then Power Strength. Five matching 30-gold shards finish each emblem. This is a baseline build, not a proven optimum.
- Bank at 40 carried gems, near an altar, when holding the winning amount, or late in the match. Recall below 32% health, move away from nearby attackers first, and stay at spawn until healed. Non-Tavi champions also recall with 150 gold and an empty gem bag.
- Place personal wards periodically toward the route. Vision is personal; shared camp claims coordinate assignments but do not reveal unseen enemy statistics.

## Evidence and limitations
The first full suite won 14/18 against starter-python, on nine maps from both sides. It lost both sides on Corners and Lanes. Replay stdout revealed 117 caught errors despite zero engine crashes; headline crash counts alone are insufficient. Ward placement was fixed before that suite. Later changes address reset handling and dead-entity enumeration. The final-v2 directory contains the subsequent validation results as they complete.

A single starter opponent is weak evidence for tournament strength. Opponent drafts vary; paired results are not controlled seeded comparisons. Do not interpret one faster win as a general speedup. Corners has severe early deaths; Lanes has poor economic throughput. Current risk scoring uses geometric distance rather than full path distance. Enemy-aware routing, team threat reports, deliberate PvP, altar-lock handling, teleport use, consumables and map-specific draft evaluation remain to be developed. The bank routine does not explicitly break hostile altar locks.

## Reproduce
From C:\battlecode, with Python on PATH:

    python scripts/benchmark.py --label next-test
    python scripts/benchmark.py --label lanes-test --maps lanes

The script saves statistics, CLI logs, replay bundles, caught-error counts and results.csv under replays/<label>. It runs both sides of each map. Use --opponent economy-v1 for comparison with the preserved version. Source changes are uncommitted and reviewable in GitHub Desktop.

## Next experiments, in priority order
1. Eliminate remaining turn errors using traceback locations in replay stdout. Check deaths after retaliatory damage and Vendetta kill resets.
2. Penalize camp choices that would consume most of current health; prioritize safe gem/gold clusters to establish equipment before elk groups.
3. Compare safer opening and equipment orders against the current version on both sides of every map; retain map-level scores and death counts.
4. Share time-stamped enemy sightings and camp respawn observations, then avoid dangerous banking routes.
5. Add hostile altar-lock removal, test teleport/consumable decisions, and evaluate against stronger independent opponents.

Latest proposed survival and reset changes are staged separately in the ChatGPT project strategy-work/bot.py; they are NOT installed or validated. Continue from those only after reviewing the differences.
