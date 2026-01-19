from __future__ import annotations

from pathlib import Path

import pytest

from ego_exo_datakit import EgoExoMcapReader


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
DOWNLOADS_ROOT = WORKSPACE_ROOT / "egocentric-quest" / "downloads"
MCAP_PATHS = sorted(DOWNLOADS_ROOT.rglob("*.mcap"))

pytestmark = pytest.mark.skipif(not MCAP_PATHS, reason="No MCAP files found under egocentric-quest/downloads")


@pytest.mark.parametrize("mcap_path", MCAP_PATHS)
def test_session_metadata_across_downloaded_mcaps(mcap_path: Path) -> None:
    reader = EgoExoMcapReader(mcap_path)
    session = reader.get_session_metadata()

    assert session.labels["version"] == "pelvis_frame"
    assert session.environment_id
    assert session.scene_id
    assert session.labels["has_exocams"] is True
    assert session.labels["num_exocams"] == 2.0
    assert reader.has_topic("/headcam/image")
    assert reader.has_topic("/camera/extrinsics")
    assert reader.exocam_names == ("exocam1", "exocam2")


def test_read_modalities_from_sample_downloaded_mcap() -> None:
    reader = EgoExoMcapReader(MCAP_PATHS[0])

    egocam = next(reader.iter_egocam_images(limit=1))
    assert egocam.camera_name == "headcam"
    assert egocam.to_numpy().shape == (egocam.height, egocam.width, 3)

    exocam = next(reader.iter_exocam_images(camera_name="exocam1", limit=1))
    assert exocam.camera_name == "exocam1"
    assert exocam.to_numpy().shape == (exocam.height, exocam.width, 3)

    left_hand = next(reader.iter_hand_keypoints("left", limit=1))
    assert "left_wrist" in left_hand.trackers
    assert left_hand["left_wrist"].pose.frame_id == "pelvis"

    upperbody = next(reader.iter_upperbody_keypoints(limit=1))
    assert "pelvis" in upperbody.trackers
    assert upperbody["pelvis"].pose.frame_id == "world"

    lowerbody = next(reader.iter_lowerbody_keypoints(limit=1))
    assert "left_hip" in lowerbody.trackers
    assert lowerbody["left_hip"].pose.frame_id == "pelvis"

    headcam_pose = next(reader.iter_camera_positions(camera_name="headcam", limit=1))
    assert headcam_pose.reference_frame == "pelvis"
    assert len(headcam_pose.position_meters_xyz) == 3

    headcam_intrinsics = reader.get_camera_intrinsics("headcam")
    assert headcam_intrinsics.image_width == egocam.width
    assert headcam_intrinsics.image_height == egocam.height

