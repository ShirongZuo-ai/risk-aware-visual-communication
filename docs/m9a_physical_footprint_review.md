# M9-A physical footprint review

The prior `0.026 m` label radius was the axle half-length, not the Webots collision footprint. The official R2025a `E-puck.proto` (SHA-256 `5503ff69e9d53b3df0501fc87cac6305ee8e558f8a78e8f70fee86f1acbf74bd`) defines the root `boundingObject` as a 24-sided cylinder of radius `0.037 m` and height `0.045 m`, plus a lower `0.05 x 0.04 m` box. Wheel cylinders project within the root cylinder. Thus the horizontal union is bounded by the orientation-invariant 0.037 m circle.

Alternatives considered were the old 0.026 m circle (rejected by 9-11 mm contact error), exact projected primitive union (same outer support but unnecessarily complex), a convex hull (orientation-dependent polygon approximation), and an empirical fitted radius (rejected as unnecessary and vulnerable to fixture tuning). The selected 0.037 m circle is directly specified by the simulator asset, deterministic, efficient for dense segment/AABB clearance, and explainable.

The historical M3 predictor uncertainty radius remains `0.037592257 m`; it is numerically close but conceptually separate and must not be substituted for the physical collision radius.
