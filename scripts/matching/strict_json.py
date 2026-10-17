"""Strict standard-JSON parsing helpers shared by calibration entry points."""

import json
import math


def _reject_non_finite_constant(token):
    raise ValueError(f'Non-finite JSON numeric constant {token!r} is not allowed')


def _parse_finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f'Non-finite JSON number {token!r} is not allowed')
    return value


def parse_json_bytes(data, label, source='<bytes>'):
    """Parse UTF-8 JSON while rejecting non-standard and overflowing numbers."""
    try:
        return json.loads(
            data.decode('utf-8-sig'),
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot parse {label} from {source}: {exc}') from exc
