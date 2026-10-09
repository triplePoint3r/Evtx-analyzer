import json
import hashlib
import shutil
import os
import stat


from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent

EVIDENCE_DIR = BASE_DIR / "evidence" # path of original copy files and hash of it
SAMPLES_DIR  = BASE_DIR / "samples" # the original data after convert it from binary to string and hash of it 
LOGS_DIR =  BASE_DIR / "logs"



def make_dir (): # make dir for files 
    for dir in [EVIDENCE_DIR, SAMPLES_DIR , LOGS_DIR]:
        dir.mkdir(parents=True, exist_ok=True)
    

def log_file(log_path: Path , action: str, detail:str):    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action" : action,
        "detail" : detail
    }
    #open log file and append detailes in every time
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def compute_hash(evtx_path: Path):
    sha256 = hashlib.sha256()
    # read binary file
    with open(evtx_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return {"sha256": sha256.hexdigest()}


def copy_original_file(evtx_path: Path , log_path: Path):    
    if not evtx_path.exists():        
        log_file(log_path, "ERROR", f"File not found: {evtx_path}")
        return None
    
    if not evtx_path.suffix.lower() == ".evtx":
        log_file(log_path, "ERROR", "Invalid file type")
        return None
        
    original_hashes = compute_hash(evtx_path)
    
    timestamp_str  = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_name  = f"{evtx_path.stem}_{timestamp_str}_EVIDENCE{evtx_path.suffix}"
    evidence_path  = EVIDENCE_DIR / evidence_name

    shutil.copy2(evtx_path, evidence_path)
    
    copied_hashes = compute_hash(evidence_path)

    integrity_ok  = (original_hashes["sha256"] == copied_hashes["sha256"])    
    log_file(log_path, "PRESERVE", f"{evtx_path.name} → {evidence_name}")

    if not integrity_ok:
        print("The Hash value is not equal. Please try again")
        print("The copied file will be deleted")
        os.chmod(EVIDENCE_DIR / evidence_name, stat.S_IWRITE)
        os.remove(EVIDENCE_DIR / evidence_name)
        return None

    return {
        "original_path":  str(evtx_path),
        "evidence_path":  str(evidence_path),
        "file_size_bytes": evtx_path.stat().st_size,
        "hashes":          original_hashes,
        "integrity":       integrity_ok,
        "preserved_at":    datetime.now().isoformat(),
    }




        
        



def get_all_evidence_files():
    """Get list of all EVTX files in evidence directory"""
    if not EVIDENCE_DIR.exists():
        return []
    return list(EVIDENCE_DIR.glob("*.evtx"))


def get_all_xml_files():
    """Get list of all XML files in samples directory"""
    if not SAMPLES_DIR.exists():
        return []
    return list(SAMPLES_DIR.glob("*.xml"))


def process_copy(evtx_path: Path):
    make_dir()
    log_path = LOGS_DIR / f"phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    result = copy_original_file(evtx_path, log_path)
    if result:
        log_file(log_path, "copy done", f"{result}")
    else:
        log_file(log_path, "copy failed", "file_data is None")    
    return result
