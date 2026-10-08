"""Read a flight-controller parameter file into {NAME: value} — no hardware involved.

Three text formats are in common use and all are accepted, detected per line:

  Mission Planner  `NAME,VALUE`                      (comments start with #)
  MAVProxy         `NAME VALUE`                      (whitespace separated)
  QGroundControl   `sysid compid NAME VALUE TYPE`    (tab separated, header lines start with #)

Lines that fit none of them are reported in `ParamFile.rejected` rather than silently dropped, so a
truncated or wrong file is visible to the operator.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

MAX_BYTES = 2 * 1024 * 1024
_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")


class ParamFileError(ValueError):
    pass


@dataclass
class ParamFile:
    params: Dict[str, float]
    format: str                                   # mission_planner | mavproxy | qgc | mixed
    duplicates: List[str] = field(default_factory=list)       # names seen more than once (last wins)
    rejected: List[Tuple[int, str]] = field(default_factory=list)  # (line number, reason)

    def to_dict(self) -> Dict:
        return {"count": len(self.params), "format": self.format, "duplicates": self.duplicates,
                "rejected": [{"line": n, "reason": r} for n, r in self.rejected], "params": dict(self.params)}


def _value(text: str) -> float:
    v = float(text)
    if not math.isfinite(v):
        raise ValueError("not a finite number")
    return v


def _parse_line(line: str) -> Tuple[str, float, str]:
    """(name, value, format) or raises ValueError with the reason."""
    if "," in line:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            raise ValueError("expected NAME,VALUE")
        name, value, fmt = parts[0], parts[1], "mission_planner"
    else:
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit():
            name, value, fmt = parts[2], parts[3], "qgc"
        elif len(parts) >= 2:
            name, value, fmt = parts[0], parts[1], "mavproxy"
        else:
            raise ValueError("expected a parameter name and a value")
    name = name.upper()
    if not _NAME.match(name):
        raise ValueError(f"'{name[:40]}' is not a parameter name")
    try:
        return name, _value(value), fmt
    except ValueError:
        raise ValueError(f"'{value[:40]}' is not a number") from None


def parse_param_text(text: str) -> ParamFile:
    if len(text.encode("utf-8", "ignore")) > MAX_BYTES:
        raise ParamFileError("Parameter file is larger than 2 MB — this does not look like a parameter file")
    params: Dict[str, float] = {}
    duplicates: List[str] = []
    rejected: List[Tuple[int, str]] = []
    formats = set()
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip().lstrip("﻿")
        if not line or line.startswith("#"):
            continue
        try:
            name, value, fmt = _parse_line(line)
        except ValueError as e:
            if len(rejected) < 50:
                rejected.append((n, str(e)))
            continue
        if name in params and name not in duplicates:
            duplicates.append(name)
        params[name] = value
        formats.add(fmt)
    if not params:
        raise ParamFileError("No parameters found — expected lines like 'FS_THR_ENABLE,1' or 'FS_THR_ENABLE 1'")
    return ParamFile(params, formats.pop() if len(formats) == 1 else "mixed", duplicates, rejected)


def parse_param_bytes(data: bytes) -> ParamFile:
    if len(data) > MAX_BYTES:
        raise ParamFileError("Parameter file is larger than 2 MB — this does not look like a parameter file")
    if b"\x00" in data[:4096]:
        raise ParamFileError("This is a binary file. Upload the text parameter file (.param / .parm / .params)")
    return parse_param_text(data.decode("utf-8", errors="replace"))
