from dataclasses import dataclass
from typing import Optional

@dataclass
class ParsedInfo:
    kind: str               # "sell" | "rent" | "unknown"
    name: Optional[str]
    amount: Optional[int]   # integer JPY (e.g., 210000) or None

@dataclass
class ProcessResult:
    path: str
    status: str             # "OK" | "ERROR" | "PENDING"
    text_length: Optional[int] = None
    new_name: Optional[str] = None
    notes: Optional[str] = None