# Battlecode strategy implementation

The active bot lives in `bots/my-bot/src`. This version implements the conditional strategies discussed in the Collision brief, strategy notes and draft review. It is a rule-based bot, not a trained model. The previous active source is preserved in `bots/pre-strategy-v2/src`.

## Draft and roles

Collision is recognised by its dimensions and altar coordinates. It drafts Varg, Willow, and Cassi & Issac. This gives four bodies: Varg for grouped damage, Willow for healing, and the linked duo for damage and capture flexibility. Cassi favours harmless resource camps. Willow follows nearby allies who need healing or face substantial damage, otherwise she farms.

Other maps use Varg/Tavi/Vendetta on grouped layouts and Vendetta/Tavi/Vesper on ungrouped layouts, adding Ryth and further picks for larger teams. From the third choice onward, two revealed control picks can trigger Marcella. It does not infer hidden enemy selections. `strategy-tavi` retains the alternative Collision draft for comparison; its source is an experiment snapshot, not maintained automatically with my-bot.

## Farming and capture

Camp scoring includes terrain-aware travel distances, reward, estimated clearing time, a conservative incoming-damage penalty, known respawns and recent enemy reports. A bounded nearby shortlist reserves enough compute to take actions. Existing capture progress receives a strong persistence bonus. Claims discourage duplicate assignments and ignore dead teammates' claims. Large camp indexes that cannot fit the compact protocol remain unclaimed rather than wrapping to the wrong group.

These are estimates, not a combat simulator. Sleeping camps are conservatively counted as potential threats. The bot does not guarantee a globally optimal route or perfect income allocation between damage dealers and capturers. Monolith remains strongly deprioritised until equipment improves.

## Communication

Live shared memory is exactly eight bytes. Bytes 0–4 contain six six-bit camp claims (zero means unassigned, group index plus one otherwise; encodable group indexes 0–62). Bytes 5–7 hold one enemy sighting: seven bits each for x and y, an eight-bit round stamp, a valid bit and a danger bit. Reports expire after eight rounds, with local token-age tracking to avoid reviving an unchanged packet after timestamp wrap.

The latest report influences camp selection and Collision teleport safety. The danger flag is reserved for richer assistance behaviour; it does not yet summon a coordinated fighting squad. Sightings do not grant personal vision or legal targeting of hidden enemies. Protocol tests check writer isolation, coordinate limits and timestamp wrap.

## Combat and survival

Targets favour achievable kills, enemy carriers, active tributes, healers and exposed Cassi. Varg values clustered targets. The bot accounts for lethal Ren retaliation before basic attacks, gives no stun bonus against Marcella, and avoids Cassi's non-damaging stun on her. Ability target categories are checked.

Shields are valued by prospective damage during their lifetime rather than waiting for a fixed health loss. Healing prioritises useful healing and nearby danger. Retreat starts below a health reserve derived from nearby threats, with a 14 percent minimum; this replaces the unconditional 32 percent rule and does not implement the unsafe “stay until 10 percent” proposal. Dash users can make conservative two-step escapes along walkable paths. General offensive dash pursuit is not implemented.

Repeated expensive queries previously allowed fuel exhaustion to resume a decision in a later round. Static camp data is cached, tactical searches are bounded, and actions check the round and remaining fuel. Budget yields are logged separately from caught errors. A narrow, logged fallback handles the engine rejecting an attack reset as already available; other exceptions retain full traceback logs.

## Banking and consumables

The existing banking triggers remain: at least 40 gems, near an altar, a bag sufficient to win, or late game. These operate on the whole bag. Hostile locks are explicitly attacked when adjacent; defensive friendly locks are placed when carried, an enemy is visible, and the altar has no lock.

Collision Varg/Tavi can buy a crystal with at least 160 gold available; locks require at least 310 gold. This avoids a universal early consumable tax. A loaded far-right carrier can use the verified lower crossing (36,5) to (33,8), mirrored for the opposite spawn, if clear and sufficiently safe. It then banks at the inner altar and recalls for resupply. Recent enemy reports suppress unsafe entry. Crystals are not assumed to be available for the return journey.

Teleport logic is specific to Collision's checked geometry and still respects occupancy. There is no general multi-teleport route planner. The carrier may delay or abandon a crystal route when unsafe. Buying tools is a heuristic, not proof each purchase is economically optimal.

## Equipment

The build completes Jungle, Monster, Bruiser Health and then repeated Power. Offensive purchases use Focus for Cassi/Stellar/Prism/Willow and Strength for others. Purchases happen where permitted, including while dead and Tavi's field shopping. No automatic selling or dynamic build search is implemented.

## Maps and validation

The published pool was refreshed to 17 maps, with the old nine-map snapshot preserved under `map-snapshots/before-strategy-update`. Refreshed map bytes were checked against the isolated pool used in testing. Current Collision contains three elk in the far-right group; old results on the one-elk/three-gem-cluster version are not interchangeable.

Run from `C:\battlecode` with Python available:

```powershell
python scripts/test_coordination.py
python scripts/benchmark.py --bot my-bot --opponent pre-strategy-v2 --label my-comparison
python scripts/benchmark.py --bot my-bot --opponent strategy-tavi --maps collision --label draft-comparison
.\tools\cambc.exe run my-bot pre-strategy-v2 --map collision --view
```

The benchmark saves JSON statistics, stdout tracebacks in replays, caught-error counts, guarded reset counts, budget-yield counts and results.csv. Use fresh labels to keep runs separate. `--map-dir` accepts a separate map snapshot. Win counts include tiebreak outcomes: a zero-gem win is not a successful delivery plan. Results against one older bot are regression evidence, not tournament win probabilities.

## Deliberately deferred

Enemy baiting into camps, coordinated ambushes, aggressive pursuit, global optimal reward allocation, precise control of Cassi–Issac separation, dynamic reinforcement squads, and general safe-tribute-window prediction remain future work. No unconditional consumable purchases, universal champion-counter table, unsupported early Monolith rush or fixed ten-percent retreat rule was added. Documents supplied by the user remain unchanged. No bot has been submitted or published.
