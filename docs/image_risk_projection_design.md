# Image Risk Projection Design

Last updated: 2026-07-18 (Asia/Shanghai)

## Scope

Milestone 4A freezes the design, terminology, interface targets, and acceptance criteria for projecting world-coordinate obstacle risk into the e-puck forward camera image. It does not implement projection algorithms, create a Webots world or controller, save frames, create masks, generate figures, implement compression, or modify accepted Milestone 3 evidence.

Milestone 3 remains the authoritative source for world-coordinate planned, state, and combined obstacle risk. The official Milestone 3 evidence remains `data/logs/m3/risk_validation_episode_0002.csv`; `risk_validation_episode_0005` is GUI reproduction evidence only.

## Source Checks Used for This Freeze

This design is based on the current project files and Webots R2025a sources checked during Milestone 4A:

- current project worlds: `simulator/worlds/minimal_epuck_camera.wbt` and `simulator/worlds/m3_world_risk_validation.wbt`;
- current project controllers and adapters that define world pose, yaw, and obstacle mappings;
- official R2025a e-puck PROTO referenced by the project worlds: `https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/robots/gctronic/e-puck/protos/E-puck.proto`;
- local Webots R2025a Camera Python API: `C:\Program Files\Webots\lib\controller\python\controller\camera.py`;
- local Webots R2025a Camera C API: `C:\Program Files\Webots\include\controller\c\webots\camera.h`;
- Webots Camera reference documentation for horizontal `fieldOfView`, inferred vertical FOV, and `near` clipping behavior.

No official file under `C:\Program Files\Webots` was modified.

## Research Question

Given:

- the current camera image;
- camera intrinsics and extrinsics;
- static obstacle 3D Boxes in world coordinates;
- per-obstacle planned, state, and combined risk scores from Milestone 3;

Milestone 4 asks how to derive:

- each obstacle's geometric projection into the camera image;
- geometric visibility and truncation status;
- a planned image risk mask;
- a state image risk mask;
- a combined image risk mask.

Milestone 4 only proves whether obstacles identified as risky in world coordinates are projected to the correct pixel support in the camera view. It does not prove compression benefit, allocate bitrate, or implement task-oriented communication.

## Coordinate Frames

### Webots World Frame

The current M1-M3 code and worlds use the Webots `x-y` plane as the ground plane and world `z` as the vertical axis. Distances are meters. Angles are radians.

Robot yaw is the heading of the e-puck local `+x` forward axis around world `+z`, computed from the Webots row-major orientation matrix as:

```text
yaw = atan2(orientation[3], orientation[0])
```

### Robot Body Frame

For the current e-puck worlds:

- origin: the e-puck Robot/Solid origin;
- `+x_body`: robot forward direction;
- `+y_body`: robot left direction;
- `-y_body`: robot right direction;
- `+z_body`: up direction.

This matches the M2 yaw definition: yaw is the rotation from world `+x` to robot `+x_body` around world `+z`.

### Webots Camera Device Frame

The current worlds instantiate the official R2025a `E-puck.proto` with:

```text
version "2"
camera_width 160
camera_height 120
camera_rotation 0 0 1 0
```

The official R2025a e-puck PROTO defines:

```text
DEF EPUCK_CAMERA Camera {
  translation 0.03 0 0.028
  rotation IS camera_rotation
  fieldOfView IS camera_fieldOfView
  width IS camera_width
  height IS camera_height
  near 0.0055
}
```

The default `camera_fieldOfView` is `0.84 rad`. In the current project, the camera is mounted at robot-local `(0.03, 0, 0.028)` with no additional camera rotation. Therefore, with the current world robot rotation at zero, the camera device origin is 30 mm forward and 28 mm above the robot origin.

Webots Camera documentation defines the Camera `fieldOfView` as the horizontal field of view, with vertical FOV inferred from aspect ratio.

Milestone 4A initially assumed that the e-puck adapter should use `diag(1,-1,-1)` from a generic Webots Camera convention. Milestone 4C tested that assumption against a real Webots R2025a e-puck RGB frame and found it incorrect for the current e-puck Camera node pose: front-visible Boxes projected outside the image while the saved RGB frame showed them in view.

The calibrated e-puck Camera adapter convention for the current R2025a world is:

- `+x_device`: optical forward direction;
- `-y_device`: image/right direction;
- `-z_device`: image/down direction.

This convention was verified in Milestone 4C with automatic RGB color-mask metrics and overlay evidence. The projection core remains generic and must not silently assume Webots or OpenCV camera coordinates.

### Project Optical Frame

The project optical frame is an internal convention used by pure projection code:

- `+z_optical`: optical forward;
- `+x_optical`: image right;
- `+y_optical`: image down.

For the calibrated Webots R2025a e-puck Camera device convention above, the fixed adapter device-to-optical transform is:

```text
x_optical = -y_device
y_optical = -z_device
z_optical =  x_device
```

Matrix form, multiplying a device-frame column vector:

```text
R_device_to_optical =
[ 0 -1  0
  0  0 -1
  1  0  0 ]
```

### Image Pixel Frame

Image pixel coordinates use:

- `u`: rightward image coordinate;
- `v`: downward image coordinate;
- top-left pixel center is `(0, 0)`;
- bottom-right pixel center is `(W - 1, H - 1)`;
- pixel-center convention is used.

The principal point is frozen as:

```text
cx = (W - 1) / 2
cy = (H - 1) / 2
```

The coordinate chain is:

```text
world point
-> camera device coordinates
-> project optical coordinates
-> image pixel coordinates
```

## Camera Intrinsics

Intrinsics must be derived from actual Camera fields, not guessed focal lengths.

For the current e-puck camera:

```text
W = 160 px
H = 120 px
horizontal_fov = 0.84 rad
near_clip_m = 0.0055 m
```

The first version assumes square pixels and an ideal pinhole camera:

```text
fx = W / (2 * tan(horizontal_fov / 2))
fy = fx
cx = (W - 1) / 2
cy = (H - 1) / 2
vertical_fov = 2 * atan((H / 2) / fy)
```

For `W=160`, `H=120`, and `horizontal_fov=0.84`, this gives:

```text
fx = 179.142225973 px
fy = 179.142225973 px
cx = 79.5 px
cy = 59.5 px
vertical_fov = 0.646372669 rad
```

Current limitations:

- zero lens distortion;
- no rolling shutter model;
- no motion blur model;
- no exposure model;
- no calibration against real image corner observations yet.

## Camera Extrinsics

The core projection interface should receive general camera models, not Webots objects:

```text
CameraIntrinsics
CameraExtrinsics
```

`CameraExtrinsics` freezes this semantic form:

```text
world_to_camera_rotation: 3x3 matrix, maps world vectors to Webots camera device vectors
world_to_camera_translation: 3-vector, maps world origin into the Webots camera device frame
device_to_optical_rotation: 3x3 matrix, maps Webots camera device vectors to project optical vectors
```

For a world point `p_world`:

```text
p_device = R_world_to_camera * p_world + t_world_to_camera
p_optical = R_device_to_optical * p_device
```

Milestone 4B may expose a precomputed `world_to_optical` 4x4 matrix as a convenience, but its semantics must remain equivalent to the chain above.

The Webots adapter, not the core projection package, is responsible for reading:

- Camera resolution;
- horizontal FOV;
- near clipping distance;
- Camera world translation;
- Camera world rotation;
- e-puck PROTO camera offset and `camera_rotation`.

Pure projection code must not call `Supervisor`, `Robot`, `Camera`, or any Webots API.

## 3D Obstacle Representation

Milestone 3 `ObstacleFootprint` is a 2D AABB and must not be modified or broken.

Milestone 4 introduces a separate 3D target structure:

```text
ObstacleBox3D:
  obstacle_id: str
  center_x: float
  center_y: float
  center_z: float
  size_x: float
  size_y: float
  size_z: float
  corners: list[8 world points]
```

Rules:

- static obstacle;
- world-coordinate frame;
- axis-aligned Box only;
- `size_x > 0`, `size_y > 0`, `size_z > 0`;
- finite numeric fields only;
- no rotated Box support in the first version;
- no arbitrary Mesh support in the first version.

The M4 Webots adapter may convert the same Webots Box into both:

- M3 `ObstacleFootprint` for world-risk calculation;
- M4 `ObstacleBox3D` for image projection.

## Frozen Data Structures

### CameraIntrinsics

```text
width_px: int
height_px: int
fx_px: float
fy_px: float
cx_px: float
cy_px: float
near_clip_m: float
```

### CameraExtrinsics

```text
world_to_camera_rotation: tuple[tuple[float, float, float], ...]
world_to_camera_translation: tuple[float, float, float]
device_to_optical_rotation: tuple[tuple[float, float, float], ...]
```

### ProjectedPoint

```text
u_px: float
v_px: float
depth_m: float
inside_image: bool
```

### ProjectedObstacle

```text
obstacle_id: str
visibility_status: str
projected_polygon: list[ProjectedPoint]
clipped_polygon: list[ProjectedPoint]
bounding_box: tuple[min_u, min_v, max_u, max_v] | None
minimum_depth_m: float | None
maximum_depth_m: float | None
projected_area_px: float
truncation_fraction: float
```

Visibility statuses are frozen as:

- `fully_visible`
- `partially_visible`
- `outside_frustum`
- `behind_camera`
- `intersects_near_plane`
- `degenerate_projection`

`fully_visible` means the geometric projection is inside the image rectangle and is not image-boundary clipped. It does not mean unobstructed real visibility, because inter-object occlusion is out of scope for the first version.

## 3D Box Projection Method

The core algorithm must not project only the obstacle center point.

The first implementation must consider:

- all 8 Box corners;
- all 12 Box edges;
- near-plane clipping in 3D;
- image-boundary clipping in 2D;
- a projected polygon, such as the 2D convex hull or equivalent projected support polygon.

Frozen rules:

1. If the full Box is behind the camera, return `behind_camera` and do not write mask pixels.
2. If the full Box is outside the camera frustum, return `outside_frustum`.
3. If some corners are behind the near plane, do not discard the Box. Clip 3D Box edges against the near plane and continue with surviving clipped geometry.
4. If the projected polygon extends beyond the image rectangle, clip it to image bounds and mark `partially_visible`.
5. If the valid projected polygon is fully inside the image rectangle, mark `fully_visible`.
6. If the projected area is below a centralized pixel tolerance, mark `degenerate_projection`.

The implementation must not use simple min/max of the 8 raw projected corner coordinates as the only projection algorithm. Raw corner min/max fails for Boxes crossing the near plane and covers many pixels that are not part of the projected support. A bounding box may still be emitted as metadata for later Object ROI baselines.

## Occlusion Boundary

Milestone 4 first version implements geometric projection and frustum visibility only.

It does not claim to solve real object-to-object occlusion. `projected_polygon` is the ideal geometric image support of the Box. `fully_visible` does not mean every pixel is visible through the rendered camera image.

Repeatable occlusion validation is deferred until a later design chooses one of:

- Webots segmentation image;
- depth buffer;
- object recognition mask;
- z-buffer rasterization;
- color-coded or marker-based validation geometry.

No document or code may claim 100% real visible area for a Box without depth, segmentation, recognition, or equivalent evidence.

## Risk to Image Masks

Milestone 4 keeps three independent image-risk channels:

- planned image risk;
- state image risk;
- combined image risk.

Each projectable obstacle receives:

- `planned_risk_score`;
- `state_risk_score`;
- `combined_risk_score`.

First mask rule:

- fill the obstacle's clipped projected polygon with that obstacle's risk value;
- background value is `0`;
- overlapping projected obstacles use `max`, not `sum`;
- mask values are clipped to `[0, 1]`;
- no unvalidated Gaussian blur;
- no dilation or mask expansion;
- no repeated projection of corridor radius or robot size;
- invisible obstacles do not write mask pixels;
- partially visible obstacles write only the image-clipped region.

The image risk mask represents the visual area of risky obstacles. It is not a filled pixel projection of the full future trajectory corridor. A projected trajectory or ground-plane corridor may be used later as a diagnostic overlay, but the first Risk ROI core should focus on obstacle visual regions so empty floor pixels are not marked as high risk merely because a corridor passes over them.

## Boundary with Compression

Milestone 4 output targets are:

- continuous image risk masks;
- obstacle polygons;
- obstacle bounding boxes;
- visibility metadata.

Compression policy conversion is deferred. Later compression work may convert these outputs into:

- Uniform;
- Center ROI;
- Object ROI;
- Risk ROI;
- JPEG/H.264/other codec quality or bit allocation.

Milestone 4A does not claim task-oriented communication, bitrate optimization, codec integration, or compression gain.

## M4 Validation Scene Design

This task does not create a world. A later M4 validation world should be independent and must not modify accepted M3 worlds.

Required future obstacle roles:

1. `CENTER_VISIBLE`: fully visible near the image center.
2. `LEFT_VISIBLE`: fully visible on the left side of the image.
3. `RIGHT_VISIBLE`: fully visible on the right side of the image.
4. `PARTIAL_IMAGE_EDGE`: clipped by an image boundary.
5. `OUTSIDE_FRUSTUM`: outside the camera frustum.
6. `BEHIND_CAMERA`: behind the camera.
7. `NEAR_PLANE_INTERSECTION`: crosses the near plane and validates 3D edge clipping.
8. `DEPTH_OVERLAP`: two Boxes overlap in projected pixels and validate mask max-union. First version does not claim true occlusion handling.

All validation Boxes should use distinct stable visual colors for manual identification only. Colors must not be algorithm inputs. The scene must avoid robot or camera collision with obstacles.

## Automatic Verification Plan

### Coordinates and Intrinsics

- optical-axis point projects to the principal point;
- a camera-right point increases `u`;
- a camera-down point increases `v`;
- only positive optical depth is projectable;
- horizontal FOV boundary behavior is correct;
- vertical FOV is derived from `fy` and image height.

### Transforms

- identity extrinsics;
- translation;
- yaw;
- pitch;
- roll;
- device-to-optical axis transform;
- world -> camera -> world round-trip error.

### 3D Box Projection

- fully visible Box;
- partially image-clipped Box;
- fully image-outside Box;
- behind-camera Box;
- near-plane intersection;
- tiny degenerate projection;
- large near Box;
- corner and edge projection consistency;
- bounding box contains clipped projected polygon.

### Risk Masks

- mask dimensions match camera image;
- values remain in `[0, 1]`;
- polygon interior receives the correct risk value;
- background remains `0`;
- overlaps use max;
- planned/state/combined channels remain independent;
- invisible obstacles do not write mask pixels;
- partially visible obstacles write only the image-clipped polygon.

### Webots Alignment

- save RGB frame and snapshot metadata;
- overlay direction matches the real camera image;
- left/right is not mirrored;
- up/down is not inverted;
- projected Box covers the corresponding obstacle;
- error metrics have explicit pixel units;
- GUI human acceptance cannot be replaced by Codex.

## Projection Error Metrics

### Corner Reprojection Error

If reliable visible Box corners or marker points are available:

- mean error in px;
- median error in px;
- max error in px.

### Bounding-Box Agreement

If Webots recognition, segmentation, or another repeatable image truth source is used:

- projected box IoU;
- polygon mask IoU;
- center error in px;
- width/height relative error.

### Manual Overlay Acceptance

Manual overlay acceptance may support but not replace automatic validation. It checks:

- left/right direction;
- up/down direction;
- projected size;
- truncation position;
- corresponding obstacle ID.

Manual screenshots alone cannot establish numeric projection accuracy.

If the e-puck Camera cannot provide recognition or segmentation truth in the final M4C setup, M4C must explicitly choose a repeatable alternative, such as color thresholds, visible corner markers, an independent Supervisor projection baseline, or custom Camera recognition configuration. This must be checked against Webots R2025a before being claimed.

## Module Boundary Plan

The planned files are not created in Milestone 4A.

### perception/camera_models.py

- `CameraIntrinsics`;
- `CameraExtrinsics`;
- `ObstacleBox3D`;
- `ProjectedPoint`;
- `ProjectedObstacle`;
- validation.

### perception/camera_projection.py

Pure-Python geometry:

- rigid transform;
- pinhole projection;
- near-plane clipping;
- image polygon clipping;
- convex hull or equivalent projected support polygon;
- 3D Box projection.

It must not import Webots, OpenCV, NumPy, ROS, or ML libraries unless a later milestone records a dependency decision that changes this boundary.

### risk_map/image_risk_map.py

- planned/state/combined masks;
- polygon rasterization;
- overlap max-union;
- image risk metadata.

### simulator/adapters/webots_camera_adapter.py

- read Camera width, height, FOV, and near;
- read Camera world pose;
- read 3D Box center and size;
- save RGB frame and snapshot metadata;
- convert Webots objects to generic models.

Webots API calls must remain in `simulator/adapters`, not in `perception` or core `risk_map` modules.

## Dependency Decision

Milestone 4A compares these options:

1. Pure Python standard library: best for auditable core geometry and consistent with M3.
2. NumPy: useful later for array/matrix speed and masks, but not necessary for first geometry core.
3. OpenCV: useful for image validation and polygon/mask operations, but heavier and should be deferred until a concrete validation need is confirmed.
4. Pillow: appropriate for image file IO and simple mask/image outputs when M4C/M4D starts writing image artifacts.

Frozen first choice:

- core camera models and projection geometry should use the Python standard library first;
- mask rasterization may use standard library initially, with Pillow allowed later for image file IO if needed;
- OpenCV is deferred until automatic image validation requires it;
- Shapely is not introduced;
- ML frameworks are not introduced.

Do not implement unreliable custom image file encoders merely to avoid dependencies. Image file IO should use Webots camera saving or a documented image library decision.

## Data and Output Plan

Later M4C may write:

```text
data/logs/m4/projection_validation_episode_XXXX.csv
data/frames/m4/...
data/metadata/m4/...
```

Projection CSV fields should include at least:

- `episode_id`
- `snapshot_time_s`
- `frame_path`
- `width_px`
- `height_px`
- `horizontal_fov_rad`
- `fx_px`
- `fy_px`
- `cx_px`
- `cy_px`
  - Camera world pose
- obstacle ID
- obstacle 3D center and size
- visibility status
- projected polygon
- clipped polygon
- bounding box
- minimum depth
- maximum depth
- projected area
- truncation fraction
  - planned risk
  - state risk
  - combined risk

Bulk data and generated results remain ignored by Git.

Milestone 4C produces a projection-only calibration dataset and intentionally omits planned, state, and combined risk fields. Milestone 4D is responsible for adding image-risk mask and risk-score fields after projection alignment is accepted.

## Milestone 4B and 4C Acceptance Targets

Milestone 4B should implement only the pure projection core and its unit tests. Acceptance requires coordinate, transform, 3D Box, clipping, and mask-rule tests without Webots dependency.

Milestone 4C should connect the core to Webots through an adapter, create a separate projection validation scene, save RGB/snapshot metadata, and validate projection alignment. GUI review is supplemental and must be recorded separately from automatic metrics.

Milestone 4D should create image-space risk masks and diagnostics from validated projection outputs. Compression remains a later step unless the roadmap explicitly advances to compression policy work.
