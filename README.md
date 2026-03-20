# ego-exo-datakit

`ego-exo-datakit` is a small Python package for reading ego/exo MCAP files.

It exposes helpers for:

- egocam images
- exocam images
- hand keypoints
- upper-body keypoints
- lower-body keypoints
- camera poses
- session metadata such as environment and scene

## Install

```bash
cd ego-exo-datakit
pip install -e .
```

## Schema Layout

Common topics:

- `/session`: session labels and stream metadata
- `/file_metadata`: per-file stream coverage
- `/headcam/image`: egocam JPEG frames
- `/headcam/intrinsics`: egocam intrinsics
- `/headcam/extrinsics`: egocam pose
- `/exocam1/image`, `/exocam2/image`: exocam JPEG frames
- `/exocam1/intrinsics`, `/exocam2/intrinsics`: exocam intrinsics
- `/exocam1/extrinsics`, `/exocam2/extrinsics`: exocam poses
- `/hand/tracking/left`, `/hand/tracking/right`: hand keypoints
- `/upperbody/tracking`: pelvis plus upper-body keypoints
- `/lowerbody/tracking`: lower-body keypoints
- `/upperbody/exo_view_tracking`, `/lowerbody/exo_view_tracking`: optional exo-view body tracks
- `/sync`: last timestamp by topic

## Pelvis Frame Convention

The converter writes session label `version=pelvis_frame`. In practice that means:

- The robotics frame convention used by the converter is `+X forward`, `+Y left`, `+Z up`.
- Hand keypoints are stored in pelvis coordinates.
- Upper-body and lower-body keypoints are also stored in pelvis coordinates.
- The `pelvis` tracker inside `/upperbody/tracking` is the exception: it is stored in `world` frame and includes orientation.
- Camera pose topics are written from the converter as pose-like records in pelvis coordinates. The translation field is used as the camera position expressed in the pelvis frame, and the rotation is the camera orientation in that same frame.

## Python API

```python
from ego_exo_datakit import EgoExoMcapReader

reader = EgoExoMcapReader("path/to/file.mcap")

session = reader.get_session_metadata()
print(session.environment_id, session.scene_id)

first_ego = next(reader.iter_egocam_images(limit=1))
rgb = first_ego.to_numpy()

first_exo = next(reader.iter_exocam_images(camera_name="exocam1", limit=1))

left_hand = next(reader.iter_hand_keypoints("left", limit=1))
print(left_hand["left_wrist"].pose.position_meters_xyz)

upper = next(reader.iter_upperbody_keypoints(limit=1))
pelvis_world = upper["pelvis"].pose.position_meters_xyz

lower = next(reader.iter_lowerbody_keypoints(limit=1))

headcam_pose = next(reader.iter_camera_positions(camera_name="headcam", limit=1))
print(headcam_pose.position_meters_xyz, headcam_pose.reference_frame)
```

## Example Scripts

Each script below takes `--mcap /path/to/file.mcap`.

- `scripts/show_schema.py`: print the topic layout and message counts
- `scripts/read_metadata.py`: print session and file metadata
- `scripts/read_egocam_images.py`: inspect and optionally save egocam frames
- `scripts/read_exocam_images.py`: inspect and optionally save exocam frames
- `scripts/read_keypoints.py`: print example hand, upper-body, and lower-body keypoints
- `scripts/read_camera_positions.py`: print camera intrinsics and pose samples

### Metadata

```bash
python scripts/read_metadata.py --mcap /path/to/file.mcap
```

### Egocam Images

```bash
python scripts/read_egocam_images.py \
  --mcap /path/to/file.mcap \
  --count 2 \
  --output-dir ./tmp_frames
```

### Exocam Images

```bash
python scripts/read_exocam_images.py \
  --mcap /path/to/file.mcap \
  --camera exocam1 \
  --count 2
```

### Keypoints

```bash
python scripts/read_keypoints.py --mcap /path/to/file.mcap
```

### Camera Poses

```bash
python scripts/read_camera_positions.py --mcap /path/to/file.mcap
```
