# Battlecode strategy implementation

## Replay corpus iteration - 29 October 2026

On the recognised Islands layout only, the camp selector removes disconnected camps before taking its nearest-ten shortlist. The previous order let ten unreachable inner-island camps hide every reachable gem route. `islands_bot.py` subclasses the existing economy controller; `main.py` selects it using the exact dimensions and ten altar coordinates. Other map controllers retain their selection policy.

The economy controller now samples visible target positions and health once during area-damage planning and scores candidate centres from those local snapshots. The samples are discarded on every cast call; no action occurs while comparing choices. Unit objects remain distinct across champion/camp handles, and budget checks guard both sampling and scoring. This reduces repeated SDK getters for Ryth's area attack without changing the non-area ability branches, gear or draft order. Separate Rows/tactical spell implementations are preserved.

`scripts/index_replay_archives.py` indexes the supplied ZIPs and extracts only matches whose filenames contain the requested team in a team slot. `scripts/decode_historical_replays.cjs` reads engine 1.0.3 replays through the official visualiser WASM and snapshot parser; set CAMBC_VISUALISER_ASSETS to the matching official asset directory. The decoder deliberately rejects other replay versions. Historical replay findings and current engine 2.0.0 tests are separate cohorts. See the current results section for outcomes and trade-offs.

## Road of Riches recall — 28 October 2026

On the recognised Road of Riches layout only, ordinary champions treat a camp as an immediate recall threat only while it is awake. This prevents a recovering champion repeatedly walking away from a dormant monster that cannot interrupt the recall. Visible enemy champions and awake in-range monsters retain the previous escape logic. The current `CurrentContent` and `Reliable` policies remain the base; the separate Rows controller is preserved. `road_reliability.py` contains the conditional controller. Full test outcomes and remaining errors are at the top of STRATEGY-RESULTS.md.

The recorded test pool contains 70 official layouts. Use `python scripts/benchmark_pool.py --bot my-bot --opponent pre-strategy-v2 --jobs 4 --label fresh-pool-test` for both sides of that recorded snapshot, or add `--maps 00road-of-riches` for a focused run. Labels must be new. The tracked pool manifest and hash validation prevent accidentally testing only the 17 legacy layouts or silently using edited maps.

## CAMSTAT-driven passive correction - 27 October 2026

The active bot now recognizes Jungle Emblems of Strength, Focus and Health when estimating neutral-camp damage. The passive belongs to the family, so counting only Strength understated survivability for Focus/Health builds. Each camp-selection call now reads inventory once and reuses that snapshot. This applies to bot.py, economy_bot.py, rows_bot.py and camp_policy.py; equipment.py contains the shared predicate. Drafts, item purchases, banking thresholds and movement policy were not changed in this iteration. All fifteen installed Python modules match the tested camstat-passives-v1 snapshot exactly.

The data review used official cambc 4.0.0 summary decoding on 128 explicitly listed files plus seven additional matches involving team 48016704-2f30-4bb9-8c37-9b6a766e53af. The 135 distinct summaries cover 216 teams, all on engine 1.0.3. The full download directory contains 24,793 files; this review does not claim to cover all of them. Your eight historical games were all losses, with 219 deaths (195 PvP, 24 camps), 4,200 gems acquired, 2,572 deposited, 1,461 lost on death, and 167 still carried. Winning other-team observations deposited 88.0% of acquired gems versus 61.2% for your sample. These historical summaries do not identify today's bot build, and the cohort is not a random ladder sample. Some matches overlap the earlier PDF evidence.

Other-team builds suggested testing Durability Health instead of Bruiser Health; it won only 3/8 against the frozen pre-change bot and was rejected. A separate 120-round bag-age banking trigger split 4/8 and was not promoted. Tavi Strength and Focus builds both occur among winners, so the data does not justify a universal Focus conversion. PvP survival and safe gem delivery remain the main unresolved historical weaknesses; the passive correction does not by itself establish reduced PvP deaths.

The prior active source is frozen in bots/before-camstat-1027. The reusable scripts/analyze_camstats.py consumes official decoded JSON, identifies teams from original ranked filenames, reconciles deposits/deaths/gem loss, and writes reproducible aggregate evidence. Inputs and analysis are indexed in replays/camstat-analysis. The CLI 4.0.0 download is isolated under work/camstat-review; tools/cambc.exe and SDK configuration were not replaced.

## PDF-driven reliability update - 27 October 2026

All three controllers now select enemy altar locks explicitly, verify attack range, and recheck readiness and occupancy before each movement attempt. Release logging prints concise errors; full tracebacks require main.DEBUG, and expected budget exits are quiet.

The economy and tactical controllers use reliability.py to snapshot retreat/dash threats into positions and ranges, reject guarded decisions after death or round rollover, and detect sustained unproductive goals. Tracking uses resources, target health, best distance and recent positions. Sixty unproductive farm turns release a failed goal for thirty rounds, banking carried gems first. Sixty unproductive movement turns trigger a six-round detour around recent loop tiles. Channels and observation gaps reset history. Goal diagnostics require reliability.DEBUG.

Rows retains its original controller and camp borrowing policy, with the direct lock and movement checks only. Its shared-wrapper experiment lost both games against the older opponent, so that integration was removed. The original bot is preserved in bots/before-pdf-1027.

Broad objective/danger changes, Tavi Power Focus purchases and the existing ranged-boss controller were tested separately and not promoted because results regressed or split by side. Drafts and item builds remain unchanged. Boss-only scoring, high-Focus enemy spell danger, recall survival and reproduction of the report's original long-stall layouts remain unresolved. This is a targeted reliability update, not a demonstrated general strength increase.

The 21 offline tests include simultaneous friendly/enemy locks, short cycles, productive combat, goal churn, observation gaps, dead actors, retreat snapshots and sixty-turn reassignment. Benchmark CSVs additionally record acquired/carried/lost gems, gold spent and opponent deaths. Printed budget-yield counts are not hard exhaustion measurements; release logging suppresses these messages. First-gem timing and camp/PvP death attribution were not instrumented.


## Rows idle-camp borrowing — 22 October 2026

Rows keeps its distinct primary camp assignments, but after round 40 a teammate may borrow another living champion's camp when that owner has explicitly released its shared claim, for example to bank or recover. Borrowed camps receive a 0.6 score multiplier so personal assignments remain preferred. Any camp actively claimed by a living teammate is excluded, including when its primary owner returns. A borrower may finish a capture already in progress if the owner resumes farming elsewhere, but does not retain an indefinite lease on a long fight. Dead owners' camps remain available as before.

Only `rows_bot.py:choose_group` changes. Drafting, combat, gear, retreat, banking, all other maps and the eight-byte protocol remain unchanged. Idle owners who retain a claim are not detected by this change. The previous active bot is preserved as `before-camp-borrowing`. Results include one loss against an older opponent; this is not a universal performance guarantee.


## Rows assignment policy — 22 October 2026

This update supersedes the Rows portion of the annotation update below. The active entry point selects `rows_bot.py` and `rows_draft.py` on the recognised Rows layout. These preserve `annotation-baseline` drafting, fighting, shopping, retreat and banking. Only setup and camp selection change. The broader Rows tactical rewrite remains in `bot.py` but is not selected by `main.py` on Rows.

Each champion deterministically receives a different primary home-side camp. Varg receives the nearest available grouped-monster camp first; other slots receive the nearest remaining home camps using static walking distances from spawn. Living teammates' assigned camps are excluded from each other's farming candidates. A dead owner's camp becomes available. Unassigned camps remain shared. Existing respawn observations and failed-route exclusions still apply. Enemy-side camps are discounted as fallbacks when a home route is unavailable. This is distinct ownership, not a coordinated attack formation or an order to wait indefinitely at a respawning camp.

The standalone experiment is `rows-assignment-v1`. The pre-promotion active bot is preserved as `before-rows-assignment`. Other map policies are unchanged. Three offline assignment tests cover unique ownership, Varg's grouped-monster preference, ordering consistency and short/empty camp pools. Benchmark results and limitations are recorded at the top of `STRATEGY-RESULTS.md`.


## Annotation update — 22 October 2026

The active entry point is `bots/my-bot/src/main.py`. It selects the new tactical policy (`bot.py`) for the recognised Packs, Eight and Rows layouts. Other layouts use `economy_bot.py`, the preserved economy policy plus the recent-damage retreat safeguard. Layout detection uses dimensions and altar positions, not filenames. Unknown/edited layouts fall back to the economy policy. The complete pre-annotation bot is preserved as `annotation-baseline`.

The sections below this update describe the earlier strategy version. Where they differ, this update describes the current behaviour.

### Implemented from the replay notes

- **Recent damage:** all maps compare consecutive start-of-turn health observations. If the net loss is at least remaining health, retreat is triggered. Death resets the sample. This observes net health change, so simultaneous healing can mask some incoming damage; it is not an engine damage-event total. Existing pressure-based retreat remains in place.
- **Packs opening and home camps:** nearby gem clusters receive an early bonus. Home-side camps receive a preference, while enemy-side farming is discouraged. Rewards, travel, estimated clear time, risk and teammate claims still matter, so a distant crate is not an unconditional first destination.
- **Route stability:** the tactical policy normally re-scores its destination every four rounds, while checking visible depletion each round. A champion that stays outside its target camp for eight attempts temporarily excludes that route. Capture itself requires several phases and is not treated as a stuck move.
- **Contested crates:** enemies near gem clusters get priority over neutral monsters when in attack range. A health/Strength/Focus comparison decides whether to engage or broadcast a backup request. Nearby healthy allies can respond for up to three rounds. This is an approximate matchup estimate, not a proven champion-counter table.
- **Local numbers advantage:** healthy nearby allies can focus an isolated opponent, especially on home territory. Pursuit is bounded by visibility and distance. A nearby favorable threat can be fought before tributing. Champions carrying a winning load prioritize delivery, and emergency retreat remains higher priority than fighting.
- **Altar choice:** the tactical policy ranks reachable altars by actual static walking distance, nearby enemy risk and a small home-distance preference. It keeps its destination unless another is materially better. It finishes an already-damaged nearby guard only when the estimated clear is short and safe. It does not open every sleeping monster beside an altar.
- **Finish a camp:** before an optional deposit, a champion may complete its current capture or finish a visible group requiring roughly three attacks with sufficient health. This does not delay delivery of a winning team load.
- **Rows roles:** draft Varg, Tavi, Vendetta, then Ryth. Varg and Ryth prefer home-side monster farming; Vendetta and Tavi prefer gem clusters. These are assignment preferences, not fixed formation movement. Monolith groups require a healthy nearby pair and adequate estimated combat capacity; on Rows the pair must include Vendetta and Tavi. Fallback attacks/spells also check that a boss group was intentionally selected. Incidental area damage can still affect nearby units.
- **Winning load:** in the tactical policy, submitted gems plus known team-carried gems reaching 1,000 makes carriers deliver immediately. Unseen teammates' live inventories cannot be queried. Near the endgame, shared memory switches to six 10-bit carried-gem reports. The switch starts at 800 submitted gems, or when one champion's submitted-plus-carried total reaches 900. Visible allies override cached reports; dead allies count as zero. Before the switch only visible carried gems can be included. Reports can lag by an owner's turn.

### Communication and mechanical limits

The eight-byte early-game protocol retains camp claims and the enemy alert, now using the danger bit for backup requests. Urgent alerts are protected from routine overwrites briefly. The endgame protocol uses bit 39 as a mode marker and packs six gem counts around it. The switch clears old claims and reports; it is permanent for the match. Camp claims and backup messages stop in this mode, deliberately trading farming coordination for delivery information. Counts saturate at 1,023, sufficient for the 1,000-gem win check.

Tavi cannot heal: his kit is attack reset plus a damage/stun spell. Willow provides healing in compositions that include her. Tavi responds as combat support. The bot already retains the full static map, including terrain, altars, camps and path fields; memory does not reveal unseen current enemies. Local camp respawn observations persist across turns.

The broader tactical rewrite regressed Corners in repeated tests. It is not enabled there. Corners retains its earlier camp-selection and banking policy with the new recent-damage retreat check. This is an intentional limit of this release, not a claim that every requested Corners behaviour is solved.

### Interpreting the supplied analytics

Final totals match the previous test records: `match-analytics.csv` is Collision A (609 rounds); `(1)` is Corners B (584); `(2)` is Rows B (863); `(3)` is Eight B (687); `(4)` is Packs B (663). This is a match by totals and duration; the CSVs themselves have no map names or champion positions. The original Corners B game won 1,016–188. Rows B peaked at 990 submitted-plus-carried gems, Eight B at 938. Packs B first had a winning total on round 653 and won on 663.

These CSVs cannot establish what Vendetta saw on rounds 12–18, identify the champion meant by “vali,” or explain an exact movement. The changes address the structural weaknesses identified in the notes rather than inventing per-champion evidence. Crates provide gems but no gold; camps near an altar are normally neutral until attacked, so blanket crate-first or monster-first orders can reduce performance.

Run `python scripts/test_tactics.py` and `python scripts/test_coordination.py` for offline checks. Full engine comparisons and release limitations are recorded in `STRATEGY-RESULTS.md`. The legacy and tactical policies are maintained separately so unvalidated tactical changes do not silently alter every map.

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


## SDK 4 and current content update - 27 October 2026

The active bot is `bots/my-bot`, with the official CLI and SDK 4.0.0 and the current 70-map manifest. Seventeen legacy map filenames remain for reproducing old results. The current engine is 2.0.0; earlier engine 1.0.3 results are not directly comparable.

`map_profile.py` inspects rewards and camp composition, including Golems, to classify new maps without relying on filenames. Existing tactical map dispatch and established draft priorities remain. The draft fallback now covers the full 12-champion roster, including Heart of Ruin. Heart-heavy automatic drafts tested poorly and were not promoted.

`current_content.py` supplies a Heart of Ruin controller: Focus-oriented equipment, shielding under pressure, bounded offensive dash candidates, and no offensive dash during recovery or banking. It avoids pulling unselected camp groups and rejects dangerous landings. Enemy Heart dash damage uses the typed ability API, including its missing-health passive; a potentially lethal burst triggers retreat using an owned position snapshot and a movement-adjusted threat envelope. These changes extend the existing economy and tactical controllers; Rows retains its specialist controller.

All three controllers create fresh attack masks with budget checks around engine calls. This addresses observed SDK 4 attack-mask metadata failures. Recovery fields initialize before interruptible parent setup. Error logs now identify the source line. The new benchmark requests JSON explicitly and records actual gem losses, camp/PvP deaths, hard fuel exhaustion, picks, faults and errors.

The optional `bots/heart-of-ruin-sdk4` variant deliberately drafts Heart on zero-gold maps. Its 0/4 full-match screen makes it experimental, not the recommended default. Other rejected experiments included early Heart drafts, lazy routing and ranged Monolith siege. The current Monolith has range 5, so range-4 siege abilities do not safely outrange it. Boss-only and heavily guarded objectives remain unresolved strategic weaknesses.

Source backup: `bots/before-sdk4-1027`. Runtime/config/map backup: `work/before-sdk4-runtime-1027`. Full experiment logs remain under `work/sdk4-evaluation/replays`; selected evidence is in `replays/sdk4-content-update`.


## Cleared boss collection - 27 October 2026

All four camp selectors check the observed reward state before imposing boss combat requirements. A visible cleared group may be collected by a weak solo champion, and its reward no longer carries the live-boss 85% discount. Live and unseen bosses retain their combat safeguards. Rows ownership rules and enemy-danger scoring still apply. Tests cover weak collectors, active captures, tactical Rows roles, unseen/live bosses, and competition with ordinary rewards. Source backup: `bots/before-reward-fix-1027`.


## C++ migration - 27 October 2026

The active 17-module Python bot now has a C++20/WASI port in `bots/my-bot-cpp`. Native C++ analysis, benchmarking, map checking and tests are in `cpp-tools`. The Python source is preserved as `python-reference`, and `my-bot` remains recommended because the migration comparison regressed. Verification: 44 native scenarios, 1,280 differential fixtures, exact analysis parity over 135 historical matches, 70 bounded pre-final map checks, eight focused final checks, and an installed-source smoke. See `CPP-MIGRATION.txt` and `replays/cpp-migration-1027/validation.json` for exact source checkpoints and limits. No deployment was performed.


## Match-data update - 27 October 2026

All 89 supplied ranked/unranked/tournament summaries were reviewed. Released C++ changes snapshot sort keys instead of querying live SDK state in comparators; both analysis tools now cover all three match kinds (89 files instead of 36). Native validation passes 46 scenarios and 1,280 differential fixtures. Six full C++ comparisons split 3-3; the C++ candidate still lost two Packs games to Python. A carry-pursuit restriction regressed and was rejected. Python remains unchanged and recommended. See `MATCH-DATA-UPDATE.txt` and `replays/match-data-update-1027/validation.json` for exact scope, cohorts and evidence.


## 28 October 2026 - reachable support while carrying gems

The Python tactical policy now excludes channeling or unreachable allies from its
engagement support estimate while carrying gems. Actual method fixtures pass and
local release comparisons won 6/8 (Eight 4/4; Packs 2/4). See SUPPORT-UPDATE.txt
for limitations and replays/support-update-1028 for evidence. C++ cache/support
experiments were not promoted after weaker local results.
