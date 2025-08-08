from pydantic import BaseModel, Field
from typing import List, Optional

class FileExtraction(BaseModel):
    src_filename: str
    detected_type: str  # 'rent' or 'sale' or 'unknown'
    property_name: Optional[str] = None
    room_label: Optional[str] = None  # 101, 1F, etc
    area_sqm: Optional[float] = None  # sale only
    # Rent values: list of integer yen values (post tax-processing per-item if known)
    rent_values_yen: Optional[List[int]] = None
    # Sale price (yen) if sale
    sale_price_yen: Optional[int] = None
    tax_mode: Optional[str] = None  # '税込', '税別', '不明'
    confidence: float = 0.5
    # Final name suggested
    suggested_filename: Optional[str] = None

class JobStatus(BaseModel):
    job_id: str
    status: str  # queued, processing, done, error
    message: Optional[str] = None
    files: List[FileExtraction] = Field(default_factory=list)

class OverrideItem(BaseModel):
    index: int
    property_name: Optional[str] = None
    room_label: Optional[str] = None
    area_sqm: Optional[float] = None
    detected_type: Optional[str] = None
    tax_mode: Optional[str] = None
    sale_price_yen: Optional[int] = None
    rent_values_yen: Optional[List[int]] = None

class Overrides(BaseModel):
    overrides: List[OverrideItem]
