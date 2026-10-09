"""
EVTX to XML Converter Module
Converts Windows Event Log files to XML format
"""

import json
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).parent
SAMPLES_DIR = BASE_DIR / "samples"
LOGS_DIR = BASE_DIR / "logs"


def log_file(log_path: Path, action: str, detail: str):
    """Log conversion actions"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "detail": detail
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def compute_hash(file_path: Path):
    """Calculate SHA256 hash of a file"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def sanitize_xml_output(xml_string: str) -> str:
    """
    Sanitize XML output by escaping special characters and removing invalid ones
    """
    import re
    
    # Remove null bytes and control characters
    xml_string = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x84\x86-\x9F]', '', xml_string)
    
    # Additional escaping for common problematic characters
    # (python-evtx library should handle this, but just in case)
    replacements = {
        '\x00': '',  # Null
        '\x0B': '',  # Vertical tab
        '\x0C': '',  # Form feed
    }
    
    for old, new in replacements.items():
        xml_string = xml_string.replace(old, new)
    
    return xml_string


def convert_evtx_to_xml(evtx_path: Path, log_path: Path):
    """
    Convert EVTX file to XML using evtx_dump or alternative method
    
    Args:
        evtx_path: Path to the EVTX file
        log_path: Path to log file
    
    Returns:
        dict with conversion results or None if failed
    """
    
    if not evtx_path.exists():
        log_file(log_path, "ERROR", f"EVTX file not found: {evtx_path}")
        return None
    
    # Generate XML filename
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    xml_name = f"{evtx_path.stem}_{timestamp_str}.xml"
    xml_path = SAMPLES_DIR / xml_name
    
    try:
        # Try using evtx_dump (Python library)
        try:
            import Evtx.Evtx as evtx
            
            log_file(log_path, "INFO", f"Converting {evtx_path.name} to XML using evtx library")
            
            with open(xml_path, 'w', encoding='utf-8', errors='ignore') as xml_file:
                # Write XML header
                xml_file.write('<?xml version="1.0" encoding="utf-8"?>\n')
                xml_file.write('<Events>\n')
                
                # Parse EVTX and write events
                with evtx.Evtx(str(evtx_path)) as log:
                    event_count = 0
                    error_count = 0
                    
                    for record in log.records():
                        try:
                            # Get XML and sanitize it
                            record_xml = record.xml()
                            record_xml = sanitize_xml_output(record_xml)
                            
                            xml_file.write(record_xml)
                            xml_file.write('\n')
                            event_count += 1
                            
                            # Log progress every 10000 events
                            if event_count % 10000 == 0:
                                log_file(log_path, "PROGRESS", f"Converted {event_count} events")
                        
                        except Exception as e:
                            error_count += 1
                            if error_count % 100 == 0:
                                log_file(log_path, "WARNING", f"Skipped {error_count} malformed events")
                            continue
                
                xml_file.write('</Events>\n')
            
            log_file(log_path, "SUCCESS", f"Converted {event_count} events to {xml_name} ({error_count} errors skipped)")
            
        except ImportError:
            # Fallback: Try using external evtx_dump.py if available
            log_file(log_path, "INFO", "evtx library not found, trying evtx_dump.py")
            
            # Check if evtx_dump.py exists
            evtx_dump_path = BASE_DIR / "tools" / "evtx_dump.py"
            if evtx_dump_path.exists():
                result = subprocess.run(
                    ["python", str(evtx_dump_path), str(evtx_path)],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Sanitize output
                    sanitized_output = sanitize_xml_output(result.stdout)
                    
                    with open(xml_path, 'w', encoding='utf-8') as f:
                        f.write(sanitized_output)
                    
                    event_count = sanitized_output.count('<Event')
                    log_file(log_path, "SUCCESS", f"Converted using evtx_dump.py")
                else:
                    raise Exception(f"evtx_dump.py failed: {result.stderr}")
            else:
                raise ImportError("No EVTX converter available")
        
        # Calculate hash of XML
        xml_hash = compute_hash(xml_path)
        
        return {
            "evtx_path": str(evtx_path),
            "xml_path": str(xml_path),
            "xml_size_bytes": xml_path.stat().st_size,
            "xml_hash": xml_hash,
            "event_count": event_count,
            "converted_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        log_file(log_path, "ERROR", f"Conversion failed: {str(e)}")
        
        # Clean up failed XML file
        if xml_path.exists():
            xml_path.unlink()
        
        return None


def process_conversion(evtx_path: Path):
    """
    Main function to process EVTX conversion
    
    Args:
        evtx_path: Path to EVTX file
    
    Returns:
        Conversion result dictionary or None
    """
    # Ensure directories exist
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create log file
    log_path = LOGS_DIR / f"conversion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    log_file(log_path, "START", f"Converting {evtx_path.name}")
    
    # Convert EVTX to XML
    result = convert_evtx_to_xml(evtx_path, log_path)
    
    if result:
        log_file(log_path, "COMPLETE", "Conversion successful")
    else:
        log_file(log_path, "FAILED", "Conversion failed")
    
    return result
