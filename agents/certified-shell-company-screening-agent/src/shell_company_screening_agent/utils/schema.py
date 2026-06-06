from __future__ import annotations

import math
import re
from typing import Any


MISSING_VALUES = {"", "-", "--", "---", "n/a", "na", "nan", "none", "null", "None", None}


def parse_number(value: Any) -> float | None:
    """Parse public-source numeric values without guessing missing facts.

    Handles plain numbers plus common Chinese units used by market data vendors.
    Returns None when a value is missing or not parseable.
    """
    if value in MISSING_VALUES:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)

    text = str(value).strip().replace(",", "")
    if text in MISSING_VALUES:
        return None
    multiplier = 1.0
    if text.endswith("万亿"):
        multiplier = 1_000_000_000_000
        text = text[:-2]
    elif text.endswith("亿"):
        multiplier = 100_000_000
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10_000
        text = text[:-1]
    elif text.endswith("%"):
        text = text[:-1]

    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0)) * multiplier
    except ValueError:
        return None


def normalize_ticker(value: Any) -> str:
    if value in MISSING_VALUES:
        return ""
    text = str(value).strip().upper()
    text = text.replace(".HK", "").replace("HK", "") if text.endswith((".HK", "HK")) else text
    digits = re.sub(r"\D", "", text)
    if digits:
        return digits.zfill(4) if len(digits) <= 4 else digits
    return text


def is_present(value: Any) -> bool:
    return value not in MISSING_VALUES and parse_number(value) is not None
