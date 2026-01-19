#!/usr/bin/env python3

from __future__ import annotations

import argparse

from ego_exo_datakit import EgoExoMcapReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Read camera poses from an ego-exo MCAP.")
    parser.add_argument("--mcap", required=True, help="Path to an MCAP file")
    args = parser.parse_args()

    reader = EgoExoMcapReader(args.mcap)

    for camera_name in reader.camera_names:
        intrinsics = reader.get_camera_intrinsics(camera_name)
        pose = next(reader.iter_camera_positions(camera_name=camera_name, limit=1))
        print(f"Camera: {camera_name}")
        print(f"  intrinsics: fx={intrinsics.fx:.3f} fy={intrinsics.fy:.3f} cx={intrinsics.cx:.3f} cy={intrinsics.cy:.3f}")
        print(f"  image size: {intrinsics.image_width}x{intrinsics.image_height}")
        print(f"  pose frame: {pose.reference_frame} -> {pose.destination_frame_id}")
        print(f"  position: {pose.position_meters_xyz}")
        print(f"  orientation_xyzw: {pose.orientation_xyzw}")


if __name__ == "__main__":
    main()

