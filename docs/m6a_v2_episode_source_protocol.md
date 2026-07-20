# M6-A v2 episode-source protocol

`m6a-byte-fair-v2` supersedes v1 for execution only; v1 remains immutable historical evidence. v2 uses the immutable M5E base world plus the causal pre-run scene primitives in `simulator/m5e_scenarios.py`, without using M5 outputs or actual traces. Duration is 6.0 s and basic timestep is 32 ms. Progress `(0.20, 0.45, 0.70, 0.90)` is aligned by `floor(raw/0.032 + 0.5)`, producing `(1.216, 2.688, 4.192, 5.408)` s. The M2 16 s schedule remains validation-only.

This phase defines in-memory source records only. It creates no v2 lockfile, Webots run, pilot data, or scientific result.
