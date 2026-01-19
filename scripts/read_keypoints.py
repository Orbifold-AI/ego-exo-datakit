#!/usr/bin/env python3

from __future__ import annotations

import argparse

from ego_exo_datakit import EgoExoMcapReader


def _print_frame(title: str, frame, limit: int) -> None:
    print(f"{title}: ts={frame.timestamp_ns} num_trackers={len(frame.trackers)}")
    for tracker_name in list(frame.trackers.keys())[:limit]:
        tracker = frame.trackers[tracker_name]
        frame_id = tracker.pose.frame_id or "unknown"
        print(
            f"  {tracker.name:16s} frame={frame_id:7s} "
            f"position={tracker.pose.position_meters_xyz} orientation={tracker.pose.orientation_xyzw}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Read hand, upper-body, and lower-body keypoints from an ego-exo MCAP.")
    parser.add_argument("--mcap", required=True, help="Path to an MCAP file")
    parser.add_argument("--preview", type=int, default=4, help="How many keypoints to print per stream")
    args = parser.parse_args()

    reader = EgoExoMcapReader(args.mcap)

    _print_frame("left hand", next(reader.iter_hand_keypoints("left", limit=1)), args.preview)
    _print_frame("right hand", next(reader.iter_hand_keypoints("right", limit=1)), args.preview)
    _print_frame("upper body", next(reader.iter_upperbody_keypoints(limit=1)), args.preview)
    _print_frame("lower body", next(reader.iter_lowerbody_keypoints(limit=1)), args.preview)


if __name__ == "__main__":
    main()
