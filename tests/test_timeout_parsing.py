"""Tests for defensive timeout_seconds parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lambda_handler.handler import _parse_timeout_seconds


def test_missing_timeout():
    assert _parse_timeout_seconds({}) == 30.0


def test_normal_timeout():
    assert _parse_timeout_seconds({"timeout_seconds": {"N": "45"}}) == 45.0


def test_clamp_high():
    assert _parse_timeout_seconds({"timeout_seconds": {"N": "400"}}) == 300.0


def test_clamp_low():
    assert _parse_timeout_seconds({"timeout_seconds": {"N": "0"}}) == 1.0


def test_invalid_value():
    assert _parse_timeout_seconds({"timeout_seconds": {"N": "abc"}}) == 30.0


def test_empty_dict():
    assert _parse_timeout_seconds({"timeout_seconds": {}}) == 30.0
