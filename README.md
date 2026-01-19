# ego-exo-datakit

`ego-exo-datakit` is a small Python package for reading the ego/exo MCAP files produced by `egocentric-quest/ego-exo-cam-v2`.

The package is built against the MCAPs already present under [`egocentric-quest/downloads`](../egocentric-quest/downloads) and exposes helpers for:

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

The generation path in the existing repo is:

1. [`batch_process_folders.py`](../egocentric-quest/ego-exo-cam-v2/pipeline/batch_process_folders.py) orchestrates per-folder processing.
2. That script delegates per-cut work to [`run_pipeline.py`](../egocentric-quest/ego-exo-cam-v2/pipeline/run_pipeline.py).
3. [`safari_protobuf_integration_fullbody.py`](../egocentric-quest/ego-exo-cam-v2/safari_protobuf_integration_fullbody.py) converts tracking JSON plus synced videos into timestamped protobuf files:
   - `session.pb`
   - `file_metadata.pb`
   - `camera_intrinsics.pb`
   - `hand_tracking_left/*.pb`
   - `hand_tracking_right/*.pb`
   - `upperbody_tracking/*.pb`
   - `lowerbody_tracking/*.pb`
   - `camera_extrinsics/*.pb`
   - `images/*.pb`
   - per-exocam `*_intrinsics.pb`, `*_extrinsics/*.pb`, and `*_images/*.pb`
4. [`pack_safari_mcap_official.py`](../egocentric-quest/ego-exo-cam-v2/pack_safari_mcap_official.py) packs those protobuf messages into MCAP topics.
5. In batch mode, [`batch_process_folders.py`](../egocentric-quest/ego-exo-cam-v2/pipeline/batch_process_folders.py) can patch wrist orientations in-place after MCAP creation.

So the MCAP is not written directly from raw JSON. The pipeline first materializes Safari protobuf messages and then packs them into MCAP.

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
python scripts/read_metadata.py --mcap ../egocentric-quest/downloads/.../file.mcap
```

### Egocam Images

```bash
python scripts/read_egocam_images.py \
  --mcap ../egocentric-quest/downloads/.../file.mcap \
  --count 2 \
  --output-dir ./tmp_frames
```

### Exocam Images

```bash
python scripts/read_exocam_images.py \
  --mcap ../egocentric-quest/downloads/.../file.mcap \
  --camera exocam1 \
  --count 2
```

### Keypoints

```bash
python scripts/read_keypoints.py --mcap ../egocentric-quest/downloads/.../file.mcap
```

### Camera Poses

```bash
python scripts/read_camera_positions.py --mcap ../egocentric-quest/downloads/.../file.mcap
```

## Tested Data

The package and examples were written against the nine MCAPs under [`egocentric-quest/downloads`](../egocentric-quest/downloads).
