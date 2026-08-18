# M9-A-I2R dual-sided contact semantics

Status: frozen offline repair for future I2-V2. It does not reinterpret the failed I2 evidence and authorizes no Webots run.

The I2 assumption that `ContactPoint.node_id` names the collision-counterpart root is rejected. R2025a returned robot body/descendant IDs from the robot query, and the installed Python wrapper and C header expose only a world-coordinate `double point[3]` plus an integer `node_id`; neither locally inspected source defines that integer as the other collision root.

At each completed timestep the robot root is queried with descendants. Every collision-relevant environment root declared in the immutable episode configuration is independently queried with descendants. A validated pair exists only when a robot-query position and a declared-counterpart-query position have Euclidean world-coordinate distance `<= epsilon_contact`, where `epsilon_contact = 0.000001 m`. Node IDs remain diagnostics.

The tolerance is frozen before I2-V2: positions use C doubles, and `1e-6 m` is comfortably above metre-scale floating-point round-off while only `0.001 mm`, `1/26000` of the physical radius, and far below the 32 ms motion scale. It allows serialization/numerical noise without matching spatially distinct contacts. The equality boundary matches; any greater distance does not.

Eligible roots come only from scenario configuration. The four fixtures declare `M9A_OBSTACLE` or the dedicated `M9A_WALL`; floor, arena floor, robot descendants, decoration, and unrelated bodies are excluded. Future scientific configurations must enumerate every eligible obstacle/wall before execution.

All simultaneously matched roots are recorded in lexicographic DEF order. Fixture validation reports the full set. Planned scientific episodes with more than one root matched at one timestep are retained but receive `CONTACT_VALIDATION_FAILURE` and are excluded under the closed technical rule; no root is chosen opportunistically.

Adjacent positive steps and gaps shorter than 0.5 s remain one event; a gap of at least 0.5 s starts another event. Physical clearance remains diagnostic and cannot create contact truth.

Installed-source evidence:

- `C:\Program Files\Webots\lib\controller\python\controller\node.py`, lines 24-33 and 169-177: `ContactPoint` exposes `point` and `node_id`; `getContactPoints` unpacks `3di`.
- `C:\Program Files\Webots\include\controller\c\webots\contact_point.h`, lines 20-24: `WbContactPoint` contains `double point[3]`, `int node_id`, and padding.
- `C:\Program Files\Webots\include\controller\c\webots\supervisor.h`, lines 115-119: contact point APIs and the bulk `WbContactPoint` call; no stronger `node_id` meaning is stated there.

I2-V2 acceptance remains two runs each: obstacle and wall require matched dual-sided points and exactly one event; safe and stationary require no matched points and zero events; every log and dedicated engineering manifest must validate. Fixture artifacts are categorically rejected by scientific evaluators.
