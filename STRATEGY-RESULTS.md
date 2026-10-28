# Strategy integration results — 18 October 2026

## Road of Riches recall and full-pool review — 28 October 2026

The installed change is limited to the recognised Road of Riches layout (40×40, altars at (19,17)/(20,22)). Recovering champions may recall near dormant monsters; awake monsters and visible enemy champions still trigger escape. `road_reliability.py` subclasses the existing reliability controller, and `main.py` selects it only for this layout. It does not change camp selection, buying, draft order or the separate Rows controller.

The integrated candidate won both Road games against the frozen current bot and all four cross-checks against `before-camstat-1027` and `pre-strategy-v2`. It split 1/2 against `allmaps-baseline-1025`, for **7/8 Road games across four local opponents**, with zero caught errors/faults in all eight. The remaining loss scored 888–1,016. These are a small deterministic comparison, not a tournament win-rate estimate.

All **70 downloaded official layouts** were tested from both sides in release mode. Against the old `allmaps-baseline-1025` source, the frozen current bot won **40/140** (18 reaching the target) and the integrated candidate won **42/140** (20 reaching the target). Directly against the frozen current bot, the candidate won **73/140** (37 reaching the target). These totals include round-limit decisions and side effects of execution timing; they are not evidence that every map improved.

The full suites retain unresolved defects: frozen current / release-vs-old / release-vs-current caught errors are **6 / 18 / 9**; engine faults are **0 / 0 / 0**; hard fuel-exhaustion events are **8765 / 7618 / 8844**. The release's Road games are error-free, but the full-pool suite is not. Suppressed budget-yield logging must not be confused with zero hard fuel exhaustion.

The frozen current suite recorded 1,075 deaths, of which 797 were attributed to camps and 278 to champions, and 7,038 carried gems lost. Vault, Yellow Brick Road, Stampede and Tangle expose computation hotspots. Contest/Stampede still fail to collect gems in this cohort; Guardians collects gems but cannot deliver them. These remain development priorities. The five uploaded historical Team A matches are losses on Lost World (28–1,007, 23 deaths), Gold Rush (369–1,003, 20), Road of Riches (0–1,007, 6), Boss Battle (0–1,027, 11) and Rows (471–1,031, 11). Their ZIP Team B logs have different match IDs and are not treated as logs of these five Team A matches.

Universal sleeping-camp filtering won 7/16 direct checks and lost both Packs games, so it was restricted to Road. Moving-camp lookup for all champions and the older Heart draft swaps were not promoted. Existing Heart of Ruin support from the newer 27 October source is retained. The older 17-map candidate from this chat was not installed over that newer source.

All **53 offline tests** passed, including 12 recall and actual entry-point routing checks. The installed source then won a two-game Road check through the new benchmark command, with no caught errors/faults; these are integration repeats, not independent strategy samples. Source syntax and Git whitespace checks passed.

The active folder already held all 70 layouts, but `.cambc/map-pool.json` still listed 17 legacy maps. All 70 hashes were checked and the manifest corrected, with a local backup of the old metadata. The tracked `benchmarks/published-pool-2026-10-28.json` records the tested snapshot. `scripts/benchmark_pool.py` runs both sides, checks hashes and complete coverage, and preserves previous result folders. The current SDK remains 4.0.0.

Evidence: `benchmarks/road-recall-2026-10-28.json` includes source hashes, all 420 full-suite results and the four cross-checks. Raw replays remain in the local project mirror under `match-review-1026/current-workspace`. Historical analysis and current-suite detail are copied to `replays/map-review-2026-10-28`. The prior active bot is preserved locally as `before-road-recall-1028`; the tested candidate is `road-recall-1028`. No competition submission was made.

## CAMSTAT analysis and promotion - 27 October 2026

The installed Jungle-passive correction won **10/14 completed matches**, with **zero caught errors and zero engine faults**. Against before-camstat-1027 it won 6/10: Eight 2/2, Packs 1/2, Collision 1/2, Monolith 1/2, Rows 1/2. Against pre-strategy-v2 it won 4/4: Collision 2/2 and Eight 2/2. These are deterministic local comparisons on five maps against two related opponents. They do not establish a ladder win rate, a universal improvement, or reduced PvP deaths. Packs and Collision still show substantial side-dependent weaknesses.

The installed fifteen-module source matches camstat-passives-v1 byte for byte. All 24 offline tests passed, including new tests for all three Jungle stat variants, absence of completed emblems and non-stacking family detection. Source syntax and Git whitespace checks passed. Final indexed evidence and source hashes are in replays/camstat-final-validation. The final installed-source 80-round Collision smoke check is separate from full-match results.

The four result folders are camstat-passives-screen (3/4), camstat-passives-collision (1/2), camstat-passives-regression (2/4), and camstat-passives-vs-older (4/4). Failed candidates are retained separately: camstat-durability-v1 won 3/8; camstat-delivery-v1 won 4/8. Both completed without caught errors or faults, but neither was promoted. The pre-iteration bot is preserved as before-camstat-1027.

Historical analysis decoded 135 distinct CAMSTAT files using the official 4.0.0 CLI, validated gem-loss conservation, deposit totals and death attribution for every team observation, and identified eight matches involving the user's UUID. See the dated STRATEGY.md section for cohort sizes, findings and inference limits; replays/camstat-analysis/analysis.json and input-manifest.json retain the calculations and input hashes. No historical result is attributed to today's modified bot, and repeated evidence from the earlier PDF is not treated as an independent new trial.

No competition upload, active tournament submission, Git commit or push was performed.

## PDF-driven reliability release - 27 October 2026

Final policy validation: **6 wins in 10 completed matches**, with **zero caught bot errors and zero engine faults**. Both starting sides were tested on Packs, Rows and Monolith against the preserved pre-change bot (3/6), and on Packs and Rows against pre-strategy-v2 (3/4). Rows won both older-opponent games after removing the shared-wrapper experiment; the final Rows controller retains its original policy plus direct lock/movement correctness fixes. Rows and Monolith final games lost no carried gems; two Packs games against the preserved bot each lost 48 gems. These are deterministic comparisons against two related opponents, not a tournament win-rate estimate or proof of a general improvement.

The 21 offline tests passed. Source syntax/archive-content validation and Git whitespace checks passed. Final evidence is indexed in replays/pdf-final-validation/results.csv and summary.json. Those files select the final policy's games from pdf-release-core, pdf-release-monolith, pdf-release-vs-older, pdf-rows-preserved and pdf-rows-preserved-vs-older. Earlier shared-wrapper Rows games are excluded because that integration was removed; the non-Rows dispatch and source did not change during the Rows retest.

The preserved original is bots/before-pdf-1027. All pdf-* bots are experimental snapshots, not the active bot. The objective/danger rewrite lost both completed Contest games; the intermediate short-stall/retreat version lost both Contest and both Monolith games; a further retreat variant lost its completed Packs A game. Remaining tests of these failed versions were cancelled. Tavi Power Focus split 2/4 against an intermediate version. The existing siege controller split 1/2 on Contest and was not evaluated on Stampede. None of these changes was promoted.

This release fixes explicit enemy-lock targeting and immediate movement revalidation in all controllers. Economy/tactical policies also receive conservative progress fallback, primitive retreat snapshots and guarded round/death checks; full tracebacks are disabled by default. Broader spell danger, team boss coordination and the exact PDF replay layouts remain unresolved. No original replay archives were available here for reproducing the reported 540-turn spawn stall or 732-move loop. Unit tests establish detection and fallback behavior, not elimination of those original incidents. Budget-yield stdout is suppressed in release mode and does not establish zero hard fuel exhaustion. First-gem timing and camp/PvP death attribution remain unmeasured.

No competition submission, commit or push was performed. A source-only ZIP was packaged separately for the user.

## Endgame tempo experiments — 24 October 2026

Three isolated Rows changes were tested against the current camp-borrowing `my-bot`, once on each starting side. None demonstrated a clear direct improvement, so **none was promoted**. The active bot remains the tested camp-borrowing version from 22 October.

| Experiment | Wins | Candidate side A | Candidate side B |
| --- | --- | --- | --- |
| Wait for 300 gold after completing both farming emblems | 0/2 | 990–1,056, round 563 | 924–1,056, round 559 |
| Skip optional shopping after 800 submitted gems | 1/2 | 1,056–990, round 562 | 924–1,056, round 559 |
| Near victory, score camps by needed gems and estimated collection/delivery time | 1/2 | 1,056–990, round 559 | 990–1,056, round 559 |

All six matches had zero candidate deaths, caught bot errors, engine faults and budget yields. Drafting, combat and health-based retreat were unchanged. These results are deterministic local comparisons against one opponent, not statistically independent tournament trials.

Evidence: `replays/shopping-tempo-v1-vs-current`, `replays/endgame-tempo-v1-vs-current`, and `replays/finish-route-v1-vs-current`. The corresponding bots are retained as `shopping-tempo-v1`, `endgame-tempo-v1` and `finish-route-v1` for inspection. They are experiments, not recommended active replacements.

The earlier loss to `pre-strategy-v2` at 990 submitted gems also had two living champions each carrying 66 gems at match end (`replays/camp-borrowing-capture-vs-older/rows-1.json`). The existing bot already prioritizes banking when its own carried gems cover the remaining target. The problem therefore cannot be diagnosed as a missing basic win-threshold check: obtaining the final bag sooner, routing and channel completion timing must be distinguished using per-turn replay evidence. The experiments above do not establish which of those caused the loss. Exact idle time and channel interruptions were not measured here.

No active source, map, submission, commit or remote repository was changed by this experiment cycle.


## Idle-camp borrowing — 22 October 2026

The final capture-preserving borrowing policy won **5/6** Rows matches against three related versions, each tested from both sides. All six had **zero caught errors, zero engine faults and zero budget yields**.

| Opponent | Candidate side A | Candidate side B |
| --- | --- | --- |
| Active bot before this change | Win 1,056–924, round 560, 0 deaths | Win 1,056–990, round 564, 0 deaths |
| annotation-baseline | Win 1,056–858, round 556, 1 death | Win 1,056–627, round 568, 3 deaths |
| pre-strategy-v2 | Win 1,056–759, round 674, 0 deaths | Loss 990–1,023, round 878, 0 deaths |

Evidence: `replays/camp-borrowing-capture-vs-current`, `replays/camp-borrowing-capture-vs-baseline`, and `replays/camp-borrowing-capture-vs-older`. The active opponent used in the first run is now preserved as `before-camp-borrowing`.

An intermediate version that let borrowers keep a camp for a long fight lost both games against the active bot and was rejected. The installed rule preserves only a capture already in progress when the owner resumes work. The final change beat the previous active version directly but regressed on one side against the older opponent, which the earlier assignment-only version had beaten. These tradeoffs remain visible rather than being treated as an unconditional improvement.

Source/AST comparison verified that only the Rows camp-selection method changed. Syntax and Git whitespace checks passed, and the installed module is checked against the tested candidate. No draft, combat or other-map policy was changed. Idle time was not separately instrumented, so the results establish match outcomes rather than a measured reduction in idle rounds. No commit, push or submission was performed.


## Rows assignment experiment and promotion — 22 October 2026

The assignment-only experiment won **6/6 games** against three related bot versions, both starting sides. It changed only setup and camp selection relative to `annotation-baseline`; AST comparison verified that all other Bot methods were unchanged, and the draft source matched byte-for-byte. All six matches had zero caught bot errors, zero engine faults and zero budget yields.

| Opponent | Side A score / rounds | Side B score / rounds |
| --- | --- | --- |
| annotation-baseline | 1,056–858 / 586 | 1,056–693 / 592 |
| my-bot before this promotion | 1,056–594 / 584 | 1,056–660 / 589 |
| pre-strategy-v2 | 1,056–726 / 750 | 1,056–528 / 776 |

Evidence is under `replays/rows-assignment-v1-vs-baseline`, `replays/rows-assignment-v1-vs-current`, and `replays/rows-assignment-v1-vs-older`. Each contains results.csv, statistics, logs and replay bundles. The opponent named `my-bot` in the second run is now preserved as `before-rows-assignment`.

The combined entry point was then tested as `rows-integrated-v1` against `annotation-baseline`. It reproduced the two baseline wins exactly, with zero errors/faults, under `replays/rows-assignment-integrated`. These two checks verify integration; they are repeats, not two additional independent strategy samples. The tested source is installed in `my-bot` only for Rows.

All three assignment unit tests passed. Source comparison confirms other maps' policy modules were not changed during this promotion. No claim is made of statistical significance or tournament strength: these are deterministic games on one Rows layout against three related opponents. Some champions still died (1/3 against baseline, 1/1 against the former active bot, 2/0 against the older bot). Idle time and exact gems lost were not instrumented in this experiment. No commit, push or tournament submission was performed.


## Annotation release — 22 October 2026

The annotation-driven implementation is installed in `bots/my-bot/src`. `main.py` selects the tactical policy on recognised Packs, Eight and Rows layouts, and the preserved economy policy with recent-damage retreat elsewhere. `annotation-baseline` preserves the active bot from before these changes. See the dated update at the top of `STRATEGY.md` for the precise feature scope and known limits.

The completed release benchmark is `replays/annotation-release/results.csv`: **18 wins in 34 games** against `annotation-baseline`, all 17 local maps, both starting sides. There were **zero engine faults and one caught bot error**, on Stampede A. Two wins were round-limit decisions rather than reaching 1,000 gems: Contest A (0–0) and Fragment A (88–44). These are not successful delivery strategies. This opponent is the stronger pre-annotation active bot, so the result is not directly comparable to the earlier 25/34 score against `pre-strategy-v2`.

Annotated maps in that run:

| Map | Wins | Candidate gems on side A / B | Interpretation |
| --- | --- | --- | --- |
| Eight | 2/2 | 1,034 / 1,020 | Both wins, zero deaths and zero errors. |
| Packs | 1/2 | 742 / 1,044 | Mixed results; not a demonstrated improvement on both sides. |
| Rows | 0/2 | 924 / 858 | Requested role and boss safeguards are implemented, but resource collection remains weak. |
| Corners | 1/2 | 1,018 / 844 | Conservative policy retained because the broad tactical rewrite repeatedly regressed. |

The single Stampede error came from a live camp-position query during attack-reset evaluation after compute exhaustion. The final source adds budget guards around spell evaluation and caches the attack mask. **The final Stampede retest was blocked by Windows Application Control (WinError 4551) when launching `tools/cambc.exe`.** This is an operating-system execution block, not a match result. The full-suite figures above precede this final fix; no claim is made that the final source completed 34 error-free matches.

Validation: six offline tactical/protocol tests cover consecutive-health loss, exact winning totals, unfavorable stat comparisons, all six endgame memory slots, mode transition, death/deposit clearing, and the healthy Vendetta–Tavi boss requirement. Three existing shared-memory tests are also retained. Source syntax and Git whitespace checks are run at installation. Actual attack and movement behaviour is supported by the engine comparisons, not by the offline tests alone.

Once the runner is permitted by the user's Windows application policy, the pending retest is:

```powershell
python scripts/benchmark.py --bot my-bot --opponent annotation-baseline --maps stampede --label annotation-stampede-confirm
```

No submission, commit or push was performed. Older failed experimental runs remain under their individual `annotation-*` replay labels and must not be mistaken for release results.

## Installed version

The active `bots/my-bot/src` contains the strategy candidate plus the final visibility refresh in retreat decisions. The previous active source is preserved in `bots/pre-strategy-v2/src`. `strategy-tavi` preserves the alternative Collision draft for further comparison.

## Regression matches

Opponent: `pre-strategy-v2`. Tested all 17 maps from the refreshed published pool, once on each side. The pool in `maps/` was checked byte-for-byte against the isolated snapshot used for this run.

- Full suite: **25 wins in 34 matches**. Of these, 23 reached the gem target; Contest A and Stampede A were zero-gem tiebreak wins and indicate unresolved delivery problems.
- Engine faults: **0**. Caught bot errors: **3**, all in Fragment A following ward relocation and a stale enemy-visibility reference.
- The final fix refreshes visible enemies before retreat scoring. The focused retest on both sides of Fragment and Collision produced **3 wins in 4 matches, zero caught errors, and zero engine faults**. Fragment A won in 926 rounds; Fragment B still lost. Both Collision games won.
- The entire 34-match suite was not repeated after this localized fix. The full-suite and focused results are separate evidence, not a claim of 34 error-free games on the final source.
- Guarded attack-reset incidents: **0** in both runs. Budget yields are intentional turn exits, counted separately from errors.

Evidence: `replays/strategy-final-current/results.csv` and `replays/strategy-visibility-fix/results.csv`, with individual statistics, replay bundles, logs and error summaries in those folders.

## Collision draft comparison

Varg–Willow–Cassi & Issac versus Varg–Willow–Tavi split **one win each** across the two sides. This does not establish a superior lineup. Cassi & Issac remains the proposed default; Tavi remains a comparison bot. Evidence: `replays/collision-draft-comparison/results.csv`.

## Remaining weaknesses

The full suite lost both sides of Eight and Rows, and one side each of Elkring, Fragment, Monolith, Packs and Contest. Zero-gem tiebreak results on Contest and Stampede are also priority failures despite being recorded as wins. Swirl A won with 12 deaths, suggesting poor risk management there.

These deterministic comparisons against one older bot measure regression performance, not tournament win probability. Further work should focus on delivery and navigation failures on the weak maps, then test multiple opponent styles. Ambush squads, enemy baiting, offensive dashes and a general teleport route planner remain unimplemented; see `STRATEGY.md` for the exact supported scope.

The previous nine-map snapshot is in `map-snapshots/before-strategy-update`. No bot was submitted and no Git changes were committed or pushed.


## Current content validation - SDK 4, 27 October 2026

The installed source passes all 35 local unit tests. An 80-round release-mode check of the installed bot on current Packs completed with zero caught bot errors. These checks establish compatibility, not competitive strength.

The SDK 4 production baseline, before the final conditional enemy-Heart threat adjustment, won 4/6 full matches against the preserved pre-update bot: Packs 2/2, Rows 1/2, Lost World 1/2. Both Rows games reached the 2,000-round limit. There were zero caught errors and zero engine faults. Rows had zero hard fuel exhaustion; other maps still had some. The final Heart-defence source split 1/2 against the Heart experimental reference on Lost World, with zero caught errors/faults and 11/31 hard fuel events. This is a separate opponent and source check, not a combined win-rate estimate.

An earlier integration candidate passed all 70 maps for 30 rounds each with zero caught errors. That candidate differs from the installed source. A final source preflight is recorded separately; short map checks cover loading, draft and initialization, not complete-game strategy. Runner timeouts are tracked as failures and retried, never counted as passes.

The optional Heart-heavy gem-map variant lost 0-4 against the preserved bot, so it remains experimental. Full early experiment logs contain failed candidates and are not asserted error-free. Rejected drafts and routing changes have not been promoted to the active bot.

Selected CSV evidence, current map manifest and installed source hashes: `replays/sdk4-content-update`. Full evidence: `work/sdk4-evaluation/replays/production-sdk4-validation`, `production-current-heart-defence`, `content-release-gem-maps` and `content-v5-all-maps`. No competition submission or Git commit/push was performed.

The final setup-order safeguard also passes a focused 12-round release-mode check on current Packs, Quadrants, Ribs, Rows and adgato-gemcombat1: 5/5, zero caught bot errors. The earlier Quadrants runner timeout passed on a separate installed-source retry. These are bounded compatibility checks.

Completed preflight: all 70 current maps exercised with the production candidate preceding the final setup-order safeguard. First pass: 69 passed, 1 runner timeout (Quadrants), zero caught bot errors. Quadrants passed on installed-source retry. After the setup-order safeguard, all five focused installed-source checks passed. This is compatibility evidence, not 70 full-game wins. Evidence: `replays/sdk4-content-update/pre-setup-order-70-map-preflight.json`, `sdk4-installed-retry.json` and `sdk4-installed-final.json`.


## Cleared boss reward selection - 27 October 2026

The active source now separates collecting a cleared boss reward from fighting a live boss. Previously all four selectors either rejected a weak/solo collector or multiplied the cleared reward's value by 0.15. The fix applies combat requirements and that penalty only while the group has not been observed reward-available. Existing ownership, danger and reachability policies remain.

Six scenario tests exercise the actual selector methods and reproduce failures in the preserved source. The installed source passes all 41 tests. Full release-mode comparisons against `before-reward-fix-1027` produced 3/6 wins, zero caught errors, and zero engine faults:

- 00packs A: win, 1018.0–618.0 gems, 1495 rounds; hard fuel 4.
- 00packs B: loss, 749.0–1007.0 gems, 1484 rounds; hard fuel 4.
- 00rows A: loss, 944.0–944.0 gems, 2000 rounds; hard fuel 0.
- 00rows B: win, 970.0–951.0 gems, 2000 rounds; hard fuel 0.
- 00monolith A: loss, 870.0–1006.0 gems, 1427 rounds; hard fuel 10.
- 00monolith B: win, 1011.0–902.0 gems, 1389 rounds; hard fuel 10.

These comparisons cover three maps and both sides; they do not establish an overall ladder improvement. Hard fuel exhaustion remains a limitation. Reward-selection correctness is established by the scenario tests, not an assertion that every full match exercised the cleared-boss case.

Evidence: `replays/reward-capture-1027/results.csv` and its JSON summaries/replays. Previous active source: `bots/before-reward-fix-1027`. No website upload, activation, commit or push was performed.


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
