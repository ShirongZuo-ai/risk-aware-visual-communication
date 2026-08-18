# M9-A seed mapping v1

For split base `B` (`pilot=910000`, `calibration=920000`, `formal=930000`), zero-based family index `f`, zero-based parameter index `p`, and replicate `r`:

`seed = B + 1000*f + 10*p + r`

Families are ordered F1..F8; parameter sets P01..P06. Replicate ranges are pilot `0`, calibration `0..1`, and formal `0..2`. Thus the prepared corpus contains 48 pilot, 96 calibration, and 144 formal identities. Inputs are identities only; runtime observations and method results are not arguments. The six-digit namespaces and injective place values make all 288 planned seeds distinct.
