# November replay review

All seven November 8 archives were indexed: **172,006 unique replay entries**. The **260 matches involving team `48016704-2f30-4bb9-8c37-9b6a766e53af`** were extracted with ZIP CRC and SHA256 checks. Exactly 130 place the team on each side. Other teams' matches were indexed, not exhaustively decoded. The source version uploaded in these games is unknown.

## Overall results

| Metric | Our team | Opponents |
| --- | ---: | ---: |
| Wins | 137 | 123 |
| Wins reaching the gem target | 105 | 93 |
| Collected gems | 223,029 | 183,462 |
| Submitted gems | 165,895 | 164,550 |
| Carried gems lost | 47,661 | 9,207 |
| Lost / collected | 21.4% | 5.0% |
| Deaths | 4,486 | 2,898 |

Collection alone is insufficient: the team gathers more but loses much more before delivery. Ordinary wins include round-limit outcomes. The aggregate counters do not establish which code version caused a loss or identify every death's source.

## Three detailed losses

**Eight:** the selected game ended 11–1,040. Of our 57 deaths, 46 occurred on enemy champion or owned-spell actions and 11 on camp actions; opponents' six deaths were all on camp actions. Their 64 deposits had an 11-gem median, starting at round 93. Our sole deposit was 11 gems at round 1,661. This supports local threat-aware banking and disengagement rather than insisting every bag reach 40 gems.

**The Front:** the selected game ended 0–1,081. Our 16 deaths split eight on enemy actions and eight on camps. Opponents made 28 deposits, median eight gems, starting at round 94; our team made none. Vendetta held 83 gems at `(36,24)` for 720 consecutive observed rounds. Full-state samples at rounds 463, 700 and 1,000 show nearby monoliths at `(32,20)` and `(32,28)` asleep, at untouched 20,000 HP, range five and strength 200. Vendetta had 286/1,000 HP, no active channel or CC, and no enemy champion within 12 tiles.

Existing retreat code can count these dormant camps as threats. Its greedy maximum-clearance choice has a stationary saddle between them, with a wall obstructing the homeward direction. This is a reproducible explanation consistent with the observed freeze; the replay does not expose its uploaded source. The release applies the already-tested awake-only recall executor to the exact Front layout. Focused comparisons reached 40–0 on one starting side and remained scoreless on the other; the final full-pool comparison against the previous bot remained scoreless on both sides. Do not call the whole map solved.

**Homonoliths:** both teams submitted zero in the selected loss. Our Varg and Tavi remained at `(31,31)` and `(33,34)` inside their spawn, with full health and no income. Nearby monoliths were **awake**, so filtering dormant monsters cannot fix this case. Their combined pressure can repeatedly trigger recovery while local retreat stays in spawn. Opponents left spawn and earned gold, winning the round-limit decision. A safe spawn-exit/bootstrap policy remains unresolved; no such policy was silently enabled in this release.

The successful opponent pattern observed in these samples is frequent small deposits while farming near altars, plus strong punishment of isolated farmers. It is not evidence for a universal eight-gem threshold or permanently grouping every champion.

## Integration decisions

Retain v12's reachable-distance camp shortlist, cached full static geometry, near-altar and threat-aware delivery, bounded local rescue, staged initialization and refreshed combat targets. Restore existing checks that allied fighters can actually contribute through terrain. Preserve ready-boss reward collection without live-boss combat gates. Keep helpers within terrain-connected cover even after attacking. Extend dormant-monster recall handling only to the verified Front layout; do not apply that explanation to awake-monster Homonoliths.

Last-seen enemy positions are temporary risk information, never legal hidden attack targets. Static walls, holes, bushes, altars, spawns and camp metadata remain available independently of vision; dynamic enemies and blockers still require current legal observations. The eight-byte team protocol is preserved.

## Validation and reproduction

All 260 replays use engine 3.0.0 and were decoded with official `v3_0_0-DBS2ESWO.wasm` and `PanelChrome-DRtW3oWL.js`. Gem conservation passed. **234 shared counter checks across three official CLI exports passed**, including outcomes and map identity. Spent gold can exceed earned gold because sales refund purchases; an official Tavi sample confirms that this is not a shifted statistics ABI.

Detailed death attribution uses official per-substep snapshots and resolves spell owners; deposit observations use input transitions. Only the selected examples received this attribution work. The SDK5 release changed several champion/item stats from engine2; historical engine2 comparisons are separate evidence.

`scripts/decode_replays_v3.cjs INPUT_DIR OUTPUT_JSON MAP_DIR` reproduces aggregate decoding. Set `CAMBC_VISUALISER_ASSETS` to the official SDK5 visualiser `assets` directory. For selected timeline analysis, run `scripts/trace_replays_v3.cjs INPUT_DIR SELECTION_JSON OUTPUT_DIR` or `scripts/trace_deaths_v3.cjs INPUT_DIR SELECTION_JSON OUTPUT_DIR`. The selection format is an array of `{filename,map,ownSide}` records. Large raw archives/traces remain local and are not committed.
