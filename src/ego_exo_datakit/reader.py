from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from mcap.reader import make_reader
from mcap_protobuf.decoder import DecoderFactory

from .models import (
    CameraIntrinsics,
    CameraPose,
    FileStreamCoverage,
    ImageFrame,
    PoseSample,
    SessionMetadata,
    StreamInfo,
    TopicInfo,
    TrackerFrame,
    TrackerSample,
)

FILE_METADATA_TOPIC = "/file_metadata"
SESSION_TOPIC = "/session"
HEADCAM_IMAGE_TOPIC = "/headcam/image"
HEADCAM_INTRINSICS_TOPIC = "/headcam/intrinsics"
HEADCAM_EXTRINSICS_TOPIC = "/headcam/extrinsics"
LEGACY_HEADCAM_EXTRINSICS_TOPIC = "/camera/extrinsics"
LEFT_HAND_TOPIC = "/hand/tracking/left"
RIGHT_HAND_TOPIC = "/hand/tracking/right"
UPPERBODY_TOPIC = "/upperbody/tracking"
LOWERBODY_TOPIC = "/lowerbody/tracking"
UPPERBODY_EXO_VIEW_TOPIC = "/upperbody/exo_view_tracking"
LOWERBODY_EXO_VIEW_TOPIC = "/lowerbody/exo_view_tracking"

_CAMERA_ALIASES = {
    "camera": "headcam",
    "egocam": "headcam",
    "headcam": "headcam",
}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _value_to_python(value_message: Any) -> Any:
    kind = value_message.WhichOneof("kind")
    if kind is None:
        return None
    if kind == "null_value":
        return None
    if kind == "number_value":
        return float(value_message.number_value)
    if kind == "string_value":
        return str(value_message.string_value)
    if kind == "bool_value":
        return bool(value_message.bool_value)
    if kind == "struct_value":
        return {key: _value_to_python(value) for key, value in value_message.struct_value.fields.items()}
    if kind == "list_value":
        return [_value_to_python(item) for item in value_message.list_value.values]
    raise ValueError(f"Unsupported protobuf value kind: {kind}")


def _struct_to_python(struct_message: Any) -> dict[str, Any]:
    return {key: _value_to_python(value) for key, value in struct_message.fields.items()}


def _pose_from_message(pose_message: Any) -> PoseSample:
    position = tuple(float(value) for value in pose_message.position_meters_xyz[:3])
    orientation = tuple(float(value) for value in pose_message.orientation_xyzw[:4]) or None
    return PoseSample(
        position_meters_xyz=position,
        orientation_xyzw=orientation,
        frame_id=pose_message.source_frame_id or None,
    )


def _tracker_status_name(tracker_message: Any) -> str | None:
    try:
        return tracker_message.Status.Name(tracker_message.status)
    except Exception:
        raw_value = getattr(tracker_message, "status", None)
        return None if raw_value in (None, 0) else str(raw_value)


def _normalize_camera_name(camera_name: str) -> str:
    token = camera_name.strip().lower()
    return _CAMERA_ALIASES.get(token, token)


def _camera_name_from_topic(topic: str) -> str:
    if topic.startswith("/") and topic.endswith("/image"):
        return topic[len("/") : -len("/image")]
    if topic.startswith("/") and topic.endswith("/intrinsics"):
        return topic[len("/") : -len("/intrinsics")]
    if topic == LEGACY_HEADCAM_EXTRINSICS_TOPIC:
        return "headcam"
    if topic.startswith("/") and topic.endswith("/extrinsics"):
        return topic[len("/") : -len("/extrinsics")]
    raise ValueError(f"Unsupported camera topic: {topic}")


class EgoExoMcapReader:
    def __init__(self, mcap_path: str | Path):
        self.path = Path(mcap_path)
        if not self.path.is_file():
            raise FileNotFoundError(f"MCAP file not found: {self.path}")
        self._summary_cache = None
        self._session_cache: SessionMetadata | None = None
        self._file_metadata_cache: tuple[str | None, dict[str, FileStreamCoverage]] | None = None

    def _summary(self):
        if self._summary_cache is None:
            with self.path.open("rb") as stream:
                summary = make_reader(stream).get_summary()
            if summary is None:
                raise ValueError(f"MCAP summary is missing for {self.path}")
            self._summary_cache = summary
        return self._summary_cache

    @property
    def topic_infos(self) -> tuple[TopicInfo, ...]:
        summary = self._summary()
        stats = summary.statistics.channel_message_counts if summary.statistics else {}
        schemas = summary.schemas or {}
        infos: list[TopicInfo] = []
        for channel_id, channel in sorted(summary.channels.items()):
            schema = schemas.get(channel.schema_id)
            infos.append(
                TopicInfo(
                    raw_topic=channel.topic,
                    schema_name=None if schema is None else schema.name,
                    message_count=int(stats.get(channel_id, 0)),
                )
            )
        return tuple(infos)

    @property
    def topic_counts(self) -> dict[str, int]:
        return {info.raw_topic: info.message_count for info in self.topic_infos}

    @property
    def camera_names(self) -> tuple[str, ...]:
        names = [_camera_name_from_topic(info.raw_topic) for info in self.topic_infos if info.raw_topic.endswith("/image")]
        unique = sorted(set(names), key=lambda value: (value != "headcam", value))
        return tuple(unique)

    @property
    def exocam_names(self) -> tuple[str, ...]:
        return tuple(name for name in self.camera_names if name != "headcam")

    @property
    def time_range_ns(self) -> tuple[int | None, int | None]:
        stats = self._summary().statistics
        if stats is None:
            return (None, None)
        return (_optional_int(stats.message_start_time), _optional_int(stats.message_end_time))

    def has_topic(self, topic: str) -> bool:
        return topic in self.topic_counts

    def get_session_metadata(self) -> SessionMetadata:
        if self._session_cache is not None:
            return self._session_cache

        with self.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, channel, _, decoded in reader.iter_decoded_messages(topics=[SESSION_TOPIC]):
                labels: dict[str, Any] = {}
                for label in decoded.labels:
                    if label.WhichOneof("value") != "label_value":
                        continue
                    labels[label.key] = _value_to_python(label.label_value)

                streams: dict[str, StreamInfo] = {}
                for stream_metadata in decoded.streams:
                    interval = stream_metadata.key_range.interval
                    streams[stream_metadata.key_range.topic] = StreamInfo(
                        topic=stream_metadata.key_range.topic,
                        is_required=bool(stream_metadata.is_required),
                        start_ns=_optional_int(interval.start_nsec),
                        stop_ns=_optional_int(interval.stop_nsec),
                    )

                interval = decoded.interval
                self._session_cache = SessionMetadata(
                    task_id=decoded.task_id or None,
                    interval_start_ns=_optional_int(interval.start_nsec),
                    interval_stop_ns=_optional_int(interval.stop_nsec),
                    labels=labels,
                    streams=streams,
                    environment_id=labels.get("environment_id"),
                    environment_description=labels.get("environment_description"),
                    scene_id=labels.get("scene_id"),
                    scene_description=labels.get("scene_description"),
                )
                return self._session_cache

        raise ValueError(f"{self.path} does not contain a {SESSION_TOPIC} message")

    def get_file_metadata(self) -> tuple[str | None, dict[str, FileStreamCoverage]]:
        if self._file_metadata_cache is not None:
            return self._file_metadata_cache

        with self.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, _, _, decoded in reader.iter_decoded_messages(topics=[FILE_METADATA_TOPIC]):
                coverages: dict[str, FileStreamCoverage] = {}
                for key_range in decoded.stream_coverages:
                    interval = key_range.interval
                    coverages[key_range.topic] = FileStreamCoverage(
                        topic=key_range.topic,
                        start_ns=_optional_int(interval.start_nsec),
                        stop_ns=_optional_int(interval.stop_nsec),
                    )
                self._file_metadata_cache = (decoded.agent_id or None, coverages)
                return self._file_metadata_cache

        raise ValueError(f"{self.path} does not contain a {FILE_METADATA_TOPIC} message")

    def get_camera_intrinsics(self, camera_name: str) -> CameraIntrinsics:
        normalized_name = _normalize_camera_name(camera_name)
        topic = f"/{normalized_name}/intrinsics"
        if normalized_name == "headcam":
            topic = HEADCAM_INTRINSICS_TOPIC
        if not self.has_topic(topic):
            raise KeyError(f"{self.path.name} does not contain camera intrinsics topic {topic}")

        with self.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, channel, _, decoded in reader.iter_decoded_messages(topics=[topic]):
                if not decoded.sensor_intrinsics:
                    raise ValueError(f"{channel.topic} does not contain sensor_intrinsics")
                intrinsics_payload = decoded.sensor_intrinsics[0]
                if intrinsics_payload.WhichOneof("intrinsics_type") != "pinhole_camera":
                    raise ValueError(f"{channel.topic} does not contain pinhole camera intrinsics")
                pinhole = intrinsics_payload.pinhole_camera
                return CameraIntrinsics(
                    camera_name=normalized_name,
                    topic=channel.topic,
                    source_frame_id=intrinsics_payload.source_frame_id or None,
                    fx=float(pinhole.fx),
                    fy=float(pinhole.fy),
                    cx=float(pinhole.cx),
                    cy=float(pinhole.cy),
                    image_width=int(pinhole.image_width),
                    image_height=int(pinhole.image_height),
                    fov_radial_radians=float(pinhole.fov_radial_radians) if pinhole.HasField("fov_radial_radians") else None,
                )
        raise ValueError(f"{self.path} does not contain data for topic {topic}")

    def iter_images(
        self,
        camera_name: str,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        reverse: bool = False,
        limit: int | None = None,
    ) -> Iterator[ImageFrame]:
        normalized_name = _normalize_camera_name(camera_name)
        topic = f"/{normalized_name}/image"
        if normalized_name == "headcam":
            topic = HEADCAM_IMAGE_TOPIC
        if not self.has_topic(topic):
            raise KeyError(f"{self.path.name} does not contain image topic {topic}")

        emitted = 0
        with self.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, channel, message, decoded in reader.iter_decoded_messages(
                topics=[topic],
                start_time=start_time,
                end_time=end_time,
                reverse=reverse,
            ):
                yield ImageFrame(
                    timestamp_ns=int(message.log_time),
                    publish_time_ns=int(message.publish_time),
                    topic=channel.topic,
                    camera_name=normalized_name,
                    width=int(decoded.cols),
                    height=int(decoded.rows),
                    jpeg_bytes=bytes(decoded.data),
                    metadata=_struct_to_python(decoded.metadata),
                )
                emitted += 1
                if limit is not None and emitted >= limit:
                    break

    def iter_egocam_images(self, **kwargs: Any) -> Iterator[ImageFrame]:
        yield from self.iter_images("headcam", **kwargs)

    def iter_exocam_images(
        self,
        camera_name: str | None = None,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        reverse: bool = False,
        limit: int | None = None,
    ) -> Iterator[ImageFrame]:
        if camera_name is not None:
            normalized_name = _normalize_camera_name(camera_name)
            if normalized_name == "headcam":
                raise ValueError("iter_exocam_images expects an exocam name, not headcam/egocam")
            yield from self.iter_images(
                normalized_name,
                start_time=start_time,
                end_time=end_time,
                reverse=reverse,
                limit=limit,
            )
            return

        topics = [f"/{camera_name}/image" for camera_name in self.exocam_names]
        emitted = 0
        with self.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, channel, message, decoded in reader.iter_decoded_messages(
                topics=topics,
                start_time=start_time,
                end_time=end_time,
                reverse=reverse,
            ):
                yield ImageFrame(
                    timestamp_ns=int(message.log_time),
                    publish_time_ns=int(message.publish_time),
                    topic=channel.topic,
                    camera_name=_camera_name_from_topic(channel.topic),
                    width=int(decoded.cols),
                    height=int(decoded.rows),
                    jpeg_bytes=bytes(decoded.data),
                    metadata=_struct_to_python(decoded.metadata),
                )
                emitted += 1
                if limit is not None and emitted >= limit:
                    break

    def _iter_tracker_topic(
        self,
        topic: str,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        reverse: bool = False,
        limit: int | None = None,
    ) -> Iterator[TrackerFrame]:
        if not self.has_topic(topic):
            raise KeyError(f"{self.path.name} does not contain tracker topic {topic}")

        emitted = 0
        with self.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, channel, message, decoded in reader.iter_decoded_messages(
                topics=[topic],
                start_time=start_time,
                end_time=end_time,
                reverse=reverse,
            ):
                trackers: dict[str, TrackerSample] = {}
                for tracker in decoded.trackers:
                    trackers[tracker.name] = TrackerSample(
                        name=tracker.name,
                        pose=_pose_from_message(tracker.pose),
                        status=_tracker_status_name(tracker),
                        metadata=_struct_to_python(tracker.metadata),
                    )
                yield TrackerFrame(
                    timestamp_ns=int(message.log_time),
                    publish_time_ns=int(message.publish_time),
                    topic=channel.topic,
                    trackers=trackers,
                )
                emitted += 1
                if limit is not None and emitted >= limit:
                    break

    def iter_hand_keypoints(self, side: str, **kwargs: Any) -> Iterator[TrackerFrame]:
        token = side.strip().lower()
        if token not in {"left", "right"}:
            raise ValueError("side must be 'left' or 'right'")
        topic = LEFT_HAND_TOPIC if token == "left" else RIGHT_HAND_TOPIC
        yield from self._iter_tracker_topic(topic, **kwargs)

    def iter_upperbody_keypoints(self, *, exo_view: bool = False, **kwargs: Any) -> Iterator[TrackerFrame]:
        topic = UPPERBODY_EXO_VIEW_TOPIC if exo_view else UPPERBODY_TOPIC
        yield from self._iter_tracker_topic(topic, **kwargs)

    def iter_lowerbody_keypoints(self, *, exo_view: bool = False, **kwargs: Any) -> Iterator[TrackerFrame]:
        topic = LOWERBODY_EXO_VIEW_TOPIC if exo_view else LOWERBODY_TOPIC
        yield from self._iter_tracker_topic(topic, **kwargs)

    def iter_camera_positions(
        self,
        camera_name: str | None = None,
        *,
        include_legacy_headcam_alias: bool = False,
        start_time: int | None = None,
        end_time: int | None = None,
        reverse: bool = False,
        limit: int | None = None,
    ) -> Iterator[CameraPose]:
        if camera_name is None:
            topics = [HEADCAM_EXTRINSICS_TOPIC]
            topics.extend(f"/{name}/extrinsics" for name in self.exocam_names)
            if include_legacy_headcam_alias and self.has_topic(LEGACY_HEADCAM_EXTRINSICS_TOPIC):
                topics.append(LEGACY_HEADCAM_EXTRINSICS_TOPIC)
        else:
            normalized_name = _normalize_camera_name(camera_name)
            if normalized_name == "headcam":
                topics = [HEADCAM_EXTRINSICS_TOPIC]
                if include_legacy_headcam_alias and self.has_topic(LEGACY_HEADCAM_EXTRINSICS_TOPIC):
                    topics.append(LEGACY_HEADCAM_EXTRINSICS_TOPIC)
            else:
                topic = f"/{normalized_name}/extrinsics"
                if not self.has_topic(topic):
                    raise KeyError(f"{self.path.name} does not contain camera extrinsics topic {topic}")
                topics = [topic]

        emitted = 0
        with self.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, channel, message, decoded in reader.iter_decoded_messages(
                topics=topics,
                start_time=start_time,
                end_time=end_time,
                reverse=reverse,
            ):
                if not decoded.sensor_extrinsics:
                    continue
                pose = decoded.sensor_extrinsics[0]
                destination = pose.destination_frame_id or _camera_name_from_topic(channel.topic)
                yield CameraPose(
                    timestamp_ns=int(message.log_time),
                    publish_time_ns=int(message.publish_time),
                    topic=channel.topic,
                    camera_name=destination,
                    position_meters_xyz=tuple(float(value) for value in pose.translation_meters_xyz[:3]),
                    orientation_xyzw=tuple(float(value) for value in pose.rotation_xyzw[:4]) or None,
                    reference_frame=pose.source_frame_id or None,
                    destination_frame_id=pose.destination_frame_id or None,
                )
                emitted += 1
                if limit is not None and emitted >= limit:
                    break
