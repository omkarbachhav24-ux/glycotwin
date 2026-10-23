"""JSON safe conversion.

Sensor frames carry NaN for signals that were never recorded, for example
meal context before the first meal of the series. NaN is not valid JSON, and
replacing it with 0 would invent a measurement, so it becomes null and the
dashboard shows it as missing.
"""
from __future__ import annotations

import math
from datetime import date, datetime

import numpy as np
import pandas as pd


def jsonable(obj):
    if obj is None:
        return None
    if isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        value = float(obj)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return pd.to_datetime(obj).isoformat()
    if obj is pd.NaT:
        return None
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, np.ndarray)):
        return [jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        try:
            return jsonable(obj.item())
        except Exception:
            return str(obj)
    return obj
