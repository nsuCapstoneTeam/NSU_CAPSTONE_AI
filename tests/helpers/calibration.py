"""Shared synthetic calibration manifest fixtures for tests."""

import json
from pathlib import Path

CALIBRATION_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs" / "experiments" / "audio-similarity-calibration"
)


def load_unacquired_manifest_fixture():
    """Return a test-only manifest without mutable acquisition state."""
    manifest = json.loads((CALIBRATION_DIR / "manifest.json").read_text(encoding="utf-8"))
    for sample in manifest["samples"]:
        sample.update({
            "source_local_path": None,
            "source_sha256": None,
            "source_file_size": None,
            "decoded_duration": None,
            "decoded_frame_count": None,
            "source_sample_rate": None,
            "source_channels": None,
            "source_codec": None,
            "acquisition_method": "not_acquired",
            "source_file_kind": "unknown",
            "full_track_verified": None,
            "full_track_evidence": None,
            "prepared_local_path": None,
            "segment_start_frame": None,
            "segment_end_frame_exclusive": None,
            "prepared_sha256": None,
            "prepared_duration": None,
        })
    return manifest
