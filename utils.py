import os
import shutil
import time
from typing import List

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def cleanup_old_jobs(root: str, ttl_seconds: int = 24*3600):
    now = time.time()
    if not os.path.isdir(root):
        return
    for d in os.listdir(root):
        p = os.path.join(root, d)
        try:
            if os.path.isdir(p):
                mtime = os.path.getmtime(p)
                if now - mtime > ttl_seconds:
                    shutil.rmtree(p, ignore_errors=True)
        except Exception:
            continue

def zip_dir(src_dir: str, zip_path: str):
    shutil.make_archive(zip_path.replace('.zip',''), 'zip', src_dir)

def copy_with_name(src_path: str, dst_path: str):
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy2(src_path, dst_path)
