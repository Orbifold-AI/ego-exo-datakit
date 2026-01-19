from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image as PILImage


@dataclass(frozen=True, slots=True)
class TopicInfo:
    raw_topic: str
    schema_name: str | None
    message_count: int


@dataclass(frozen=True, slots=True)
class PoseSample:
    position_meters_xyz: tuple[float, float, float]
    orientation_xyzw: tuple[float, float, float, float] | None
    frame_id: str | None


@dataclass(frozen=True, slots=True)
class TrackerSample:
    name: str
    pose: PoseSample
    status: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TrackerFrame:
    timestamp_ns: int
    publish_time_ns: int
    topic: str
    trackers: dict[str, TrackerSample]

    def __getitem__(self, name: str) -> TrackerSample:
        return self.trackers[name]


@dataclass(frozen=True, slots=True)
class CameraIntrinsics:
    camera_name: str
    topic: str
    source_frame_id: str | None
    fx: float
    fy: float
    cx: float
    cy: float
    image_width: int
    image_height: int
    fov_radial_radians: float | None


@dataclass(frozen=True, slots=True)
class CameraPose:
    timestamp_ns: int
    publish_time_ns: int
    topic: str
    camera_name: str
    position_meters_xyz: tuple[float, float, float]
    orientation_xyzw: tuple[float, float, float, float] | None
    reference_frame: str | None
    destination_frame_id: str | None


@dataclass(frozen=True, slots=True)
class ImageFrame:
    timestamp_ns: int
    publish_time_ns: int
    topic: str
    camera_name: str
    width: int
    height: int
    jpeg_bytes: bytes
    metadata: dict[str, Any]

    def to_pil(self) -> PILImage.Image:
        if not self.jpeg_bytes:
            raise ValueError(f"{self.topic} frame at {self.timestamp_ns} has empty image bytes")
        return PILImage.open(io.BytesIO(self.jpeg_bytes)).copy()

    def to_numpy(self) -> np.ndarray:
        return np.asarray(self.to_pil())

    def save_jpeg(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.jpeg_bytes)
        return output_path


@dataclass(frozen=True, slots=True)
class StreamInfo:
    topic: str
    is_required: bool
    start_ns: int | None
    stop_ns: int | None


@dataclass(frozen=True, slots=True)
class FileStreamCoverage:
    topic: str
    start_ns: int | None
    stop_ns: int | None


@dataclass(frozen=True, slots=True)
class SessionMetadata:
    task_id: str | None
    interval_start_ns: int | None
    interval_stop_ns: int | None
    labels: dict[str, Any]
    streams: dict[str, StreamInfo]
    environment_id: str | None
    environment_description: str | None
    scene_id: str | None
    scene_description: str | None

