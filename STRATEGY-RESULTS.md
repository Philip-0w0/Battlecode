# Strategy integration results — 18 October 2026

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
