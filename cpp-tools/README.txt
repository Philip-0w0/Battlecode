Native Windows C++ tools. No Python runtime is needed.

Build and test (GCC 15 / C++20 was used):
  powershell -NoProfile -ExecutionPolicy Bypass -File cpp-tools/build.ps1
  .\cpp-tools\core-tests.exe cpp-tools/tests/python-parity.json

Run from the Battlecode workspace root, or supply --root with an absolute path:
  .\cpp-tools\cam-tools.exe benchmark --bot my-bot-cpp --opponent my-bot --maps 00packs 00rows --label cpp-comparison
  .\cpp-tools\cam-tools.exe smoke --bot my-bot-cpp --opponent sdk4-map-probe-cpp --rounds 12 --label cpp-map-check
  .\cpp-tools\cam-tools.exe analyze --directory DECODED_JSON_FOLDER --team-id 48016704-2f30-4bb9-8c37-9b6a766e53af --output analysis.json

Benchmark runs full release-mode games on both sides and saves JSON, CSV, logs
and replays. Smoke runs bounded compatibility checks. Default maps come from
.cambc/map-pool.json, excluding preserved legacy aliases.
Analysis consumes official decoded ranked_*.json, unranked_*.json and
tournament_*.json summaries. Decode CAMSTAT with
the official CLI's summary command first. Conservation checks reject bad data.

The runner launches subprocesses with Windows CreateProcessW, without a command
shell. A private job object contains each runner and enforces a timeout. Replay
stdout is read through Windows' built-in .NET ZIP API using a generated, local
PowerShell helper. Its execution-policy override applies only to that child
process and does not change Windows policy settings. No account data is read.

JSON dependency: nlohmann/json 3.12.0, MIT, vendored in vendor/.
Official release: https://github.com/nlohmann/json/releases/tag/v3.12.0
Verified json.hpp SHA256:
aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63

The parity fixture contains expected values generated once from the preserved
Python reference, with all 17 source SHA256 values. It is data; testing it uses
only the native core-tests executable. Earlier Python scripts remain available
as reference material.
