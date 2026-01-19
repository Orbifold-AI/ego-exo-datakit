#!/usr/bin/env python3

from __future__ import annotations

import argparse

from ego_exo_datakit import EgoExoMcapReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the topic layout for an ego-exo MCAP file.")
    parser.add_argument("--mcap", required=True, help="Path to an MCAP file")
    args = parser.parse_args()

    reader = EgoExoMcapReader(args.mcap)
    start_ns, end_ns = reader.time_range_ns

    print(f"MCAP: {reader.path}")
    print(f"Time range: {start_ns} -> {end_ns}")
    print(f"Cameras: {', '.join(reader.camera_names)}")
    print("Topics:")
    for info in reader.topic_infos:
        print(f"  {info.raw_topic:32s} {info.message_count:6d}  {info.schema_name}")


if __name__ == "__main__":
    main()

