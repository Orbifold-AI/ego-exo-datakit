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

If you are installing in an offline or network-restricted environment, pip build isolation may fail while trying to recreate `setuptools` in a temporary build env. In that case, use:

```bash
pip install -e . --no-build-isolation
```

## How The MCAPs Are Generated

The MCAPs consumed by this package are produced in two stages:

1. Tracking JSON plus synchronized video streams are converted into timestamped Safari protobuf messages such as:
   - `session.pb`
   - `file_metadata.pb`
   - `camera_intrinsics.pb`
   - `hand_tracking_left/*.pb`
   - `hand_tracking_right/*.pb`
   - `upperbody_tracking/*.pb`
   - `lowerbody_tracking/*.pb`
   - `camera_extrinsics/*.pb`
   - `images/*.pb`
   - per-camera `*_intrinsics.pb`, `*_extrinsics/*.pb`, and `*_images/*.pb`
2. Those protobuf messages are then packed into MCAP topics.

So the MCAP is not written directly from raw JSON. The generator first materializes protobuf messages and then packs them into MCAP.

## Schema Layout

The downloaded MCAPs currently contain these topics:

| Topic | Protobuf type | Meaning |
| --- | --- | --- |
| `/file_metadata` | `safari_sdk.protos.logging.FileMetadata` | Per-file stream coverage |
| `/session` | `safari_sdk.protos.logging.Session` | Labels and stream metadata |
| `/headcam/intrinsics` | `safari_sdk.protos.SensorCalibration` | Egocam intrinsics |
| `/headcam/extrinsics` | `safari_sdk.protos.SensorCalibration` | Egocam pose payload |
| `/headcam/image` | `safari_sdk.protos.Image` | Egocam JPEG frames |
| `/exocam1/intrinsics`, `/exocam2/intrinsics` | `safari_sdk.protos.SensorCalibration` | Exocam intrinsics |
| `/exocam1/extrinsics`, `/exocam2/extrinsics` | `safari_sdk.protos.SensorCalibration` | Exocam pose payloads |
| `/exocam1/image`, `/exocam2/image` | `safari_sdk.protos.Image` | Exocam JPEG frames |
| `/hand/tracking/left` | `safari_sdk.protos.logging.Trackers` | Left hand keypoints |
| `/hand/tracking/right` | `safari_sdk.protos.logging.Trackers` | Right hand keypoints |
| `/upperbody/tracking` | `safari_sdk.protos.logging.Trackers` | Pelvis + upper-body keypoints |
| `/lowerbody/tracking` | `safari_sdk.protos.logging.Trackers` | Lower-body keypoints |
| `/upperbody/exo_view_tracking` | `safari_sdk.protos.logging.Trackers` | Optional exo-view upper body |
| `/lowerbody/exo_view_tracking` | `safari_sdk.protos.logging.Trackers` | Optional exo-view lower body |
| `/sync` | `safari_sdk.protos.logging.TimeSynchronization` | Last timestamp by topic |

### Legacy Alias

The downloaded MCAPs also include `/camera/extrinsics`. In the tested files it duplicates the headcam pose stream. `ego-exo-datakit` treats `/headcam/extrinsics` as the canonical egocam pose topic and only exposes the legacy alias if you explicitly request it.

## Pelvis Frame Convention

The converter writes session label `version=pelvis_frame`. In practice that means:

- The robotics frame convention used by the converter is `+X forward`, `+Y left`, `+Z up`.
- Hand keypoints are stored in pelvis coordinates.
- Upper-body and lower-body keypoints are also stored in pelvis coordinates.
- The `pelvis` tracker inside `/upperbody/tracking` is the exception: it is stored in `world` frame and includes orientation.
- Camera pose topics are written from the converter as pose-like records in pelvis coordinates. The translation field is used as the camera position expressed in the pelvis frame, and the rotation is the camera orientation in that same frame.

That last point matters because the container message is a `Transform`, but the converter intentionally writes pose-style data there for validator compatibility.

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

## Tested Data

The package and examples were validated against real MCAP files.

## Running Tests

Point the test suite at any directory containing `.mcap` files:

```bash
export EGO_EXO_DATAKIT_TEST_DATA_ROOT=/path/to/mcap_dir
pytest -q
```
