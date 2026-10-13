# Engineering rules

Apply Ponytail's full mode. Read the callers, configuration, tests and data flow before editing.
Reuse the strategy registry, data cache, paper replay and event store. Prefer the standard library
and existing dependencies. Do not add a second implementation of a shared rule or a speculative
service layer. Keep the complete change readable; fewer lines are useful only after correctness.

Never remove validation, evidence provenance, safe failure behavior or risk checks to save code.
Changes to money calculations, parsers, persistence, concurrency or security need a meaningful
regression test. Mark a deliberate temporary limit with `shortcut: limit, upgrade condition`.

The studio is loopback-only and paper-only. Do not add exchange credentials or order routes as part
of an unrelated feature. Reviews cannot modify measurements, count twice or override hard checks.
Synthetic data, stale feeds and missing provenance must not produce eligible trade suggestions.

Run `make lint` and `make test` before shipping. Validate any UI change against actual run events.
Review in order: correctness, security, expected load, tests, speed, then unnecessary code.
Report concrete inputs, failures and fixes. State what was not checked. Do not claim benchmark
savings without recording measurements on this project.

Rules adapted from [Ponytail](https://github.com/DietrichGebert/ponytail), MIT licensed.
