#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

from ego_exo_datakit import EgoExoMcapReader


def main() -> None:
    parser = argparse.ArgumentParser(description="Read session metadata from an ego-exo MCAP.")
    parser.add_argument("--mcap", required=True, help="Path to an MCAP file")
    args = parser.parse_args()

    reader = EgoExoMcapReader(args.mcap)
    session = reader.get_session_metadata()
    agent_id, coverages = reader.get_file_metadata()

    payload = {
        "mcap": str(reader.path),
        "task_id": session.task_id,
        "environment_id": session.environment_id,
        "environment_description": session.environment_description,
        "scene_id": session.scene_id,
        "scene_description": session.scene_description,
        "interval_start_ns": session.interval_start_ns,
        "interval_stop_ns": session.interval_stop_ns,
        "agent_id": agent_id,
        "labels": session.labels,
        "stream_coverages": {
            topic: {"start_ns": coverage.start_ns, "stop_ns": coverage.stop_ns}
            for topic, coverage in coverages.items()
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

