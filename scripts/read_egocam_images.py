#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from ego_exo_datakit import EgoExoMcapReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Read egocam/headcam frames from an ego-exo MCAP.")
    parser.add_argument("--mcap", required=True, help="Path to an MCAP file")
    parser.add_argument("--count", type=int, default=1, help="How many frames to inspect")
    parser.add_argument("--output-dir", help="Optional directory to save the frames as JPEGs")
    args = parser.parse_args()

    reader = EgoExoMcapReader(args.mcap)
    output_dir = Path(args.output_dir) if args.output_dir else None

    for index, frame in enumerate(reader.iter_egocam_images(limit=args.count), start=1):
        print(
            f"[{index}] {frame.camera_name} ts={frame.timestamp_ns} "
            f"size={frame.width}x{frame.height} brightness={frame.metadata.get('brightness_level')}"
        )
        if output_dir is not None:
            saved_path = frame.save_jpeg(output_dir / f"egocam_{frame.timestamp_ns}.jpg")
            print(f"    saved {saved_path}")


if __name__ == "__main__":
    main()

