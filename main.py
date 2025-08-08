import os
import uuid
import json
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from models import JobStatus, FileExtraction, Overrides
from ocr_extractor import extract_from_pdf
from naming import build_filename_rent_single, build_filename_rent_range, build_filename_sale
from utils import ensure_dir, cleanup_old_jobs, zip_dir, copy_with_name

JOBS_ROOT = os.environ.get("JOBS_ROOT", "/tmp/mysoku_jobs")

app = FastAPI(title="Mysoku Renamer API", version="0.1.0")

# CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job registry (MVP)
JOBS: dict[str, JobStatus] = {}

def suggest_name(rec: FileExtraction) -> str:
    if rec.detected_type == "rent":
        if rec.rent_values_yen:
            if len(rec.rent_values_yen) >= 2:
                mn, mx = min(rec.rent_values_yen), max(rec.rent_values_yen)
                return build_filename_rent_range(rec.property_name or "", mn, mx)
            else:
                return build_filename_rent_single(rec.property_name or "", rec.room_label, rec.rent_values_yen[0])
        # fallback
        return f"【賃貸】{(rec.property_name or '物件名不明')}.pdf"
    elif rec.detected_type == "sale":
        if rec.sale_price_yen:
            return build_filename_sale(rec.property_name or "", rec.room_label, rec.area_sqm, rec.sale_price_yen)
        # fallback
        return f"【売買】{(rec.property_name or '物件名不明')}.pdf"
    return f"{(rec.property_name or '物件名不明')}.pdf"

@app.post("/api/upload", response_model=JobStatus)
async def upload(files: List[UploadFile] = File(...)):
    cleanup_old_jobs(JOBS_ROOT)
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_ROOT, job_id, "src")
    out_dir = os.path.join(JOBS_ROOT, job_id, "out")
    ensure_dir(job_dir)
    ensure_dir(out_dir)

    recs: List[FileExtraction] = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(400, detail="PDFのみアップロードしてください")
        dst = os.path.join(job_dir, os.path.basename(f.filename))
        with open(dst, "wb") as w:
            w.write(await f.read())
        # OCR & Extract
        data = extract_from_pdf(dst)
        rec = FileExtraction(
            src_filename=os.path.basename(f.filename),
            detected_type=data["detected_type"],
            property_name=data["property_name"],
            room_label=data["room_label"],
            area_sqm=data["area_sqm"],
            rent_values_yen=data["rent_values_yen"],
            sale_price_yen=data["sale_price_yen"],
            tax_mode=data["tax_mode"],
            confidence=0.6,
            suggested_filename=None
        )
        rec.suggested_filename = suggest_name(rec)
        recs.append(rec)

    status = JobStatus(job_id=job_id, status="processing", message=None, files=recs)
    # Mark instantly as done for MVP
    status.status = "done"
    JOBS[job_id] = status
    return status

@app.get("/api/job/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    st = JOBS.get(job_id)
    if not st:
        raise HTTPException(404, detail="job not found")
    return st

@app.post("/api/job/{job_id}/override", response_model=JobStatus)
async def apply_override(job_id: str, overrides: Overrides):
    st = JOBS.get(job_id)
    if not st:
        raise HTTPException(404, detail="job not found")
    for ov in overrides.overrides:
        if ov.index < 0 or ov.index >= len(st.files):
            continue
        rec = st.files[ov.index]
        if ov.property_name is not None:
            rec.property_name = ov.property_name
        if ov.room_label is not None:
            rec.room_label = ov.room_label
        if ov.area_sqm is not None:
            rec.area_sqm = ov.area_sqm
        if ov.detected_type is not None:
            rec.detected_type = ov.detected_type
        if ov.tax_mode is not None:
            rec.tax_mode = ov.tax_mode
        if ov.sale_price_yen is not None:
            rec.sale_price_yen = ov.sale_price_yen
        if ov.rent_values_yen is not None:
            rec.rent_values_yen = ov.rent_values_yen
        rec.suggested_filename = suggest_name(rec)
    return st

@app.post("/api/job/{job_id}/finalize")
async def finalize(job_id: str):
    st = JOBS.get(job_id)
    if not st:
        raise HTTPException(404, detail="job not found")
    job_src = os.path.join(JOBS_ROOT, job_id, "src")
    job_out = os.path.join(JOBS_ROOT, job_id, "out")
    ensure_dir(job_out)
    for i, rec in enumerate(st.files):
        src_path = os.path.join(job_src, rec.src_filename)
        dst_path = os.path.join(job_out, rec.suggested_filename or f"{i}.pdf")
        copy_with_name(src_path, dst_path)
    zip_path = os.path.join(JOBS_ROOT, job_id, "mysoku_renamed.zip")
    zip_dir(job_out, zip_path)
    return {"download_url": f"/api/job/{job_id}/download"}

@app.get("/api/job/{job_id}/download")
async def download(job_id: str):
    zip_path = os.path.join(JOBS_ROOT, job_id, "mysoku_renamed.zip")
    if not os.path.isfile(zip_path):
        raise HTTPException(404, detail="zip not found")
    # NOTE: You may delete files after sending in production via a background task
    return FileResponse(zip_path, filename="mysoku_renamed.zip", media_type="application/zip")
