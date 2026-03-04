#!/usr/bin/env python3
"""
KeyProgrammer Parser - CLI Version
Command-line interface for extracting VINs from Autel/XTool device dumps
"""

import chardet
import os
import sys
import zipfile
import tempfile
import shutil
import re
import pandas as pd
from vininfo import Vin
import pyvin
import datetime
import sqlite3
import platform
import textwrap
import json
from ipaddress import ip_address, IPv4Address, IPv6Address
from jinja2 import Template, Environment, FileSystemLoader
import gzip
import stat
import time
import gc
import argparse

# Helper: safe rmtree that tolerates read-only files and locked files on Windows
def _on_rm_error(func, path, exc_info):
    """Attempt to make a file writable and retry the failed operation."""
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except Exception:
        pass

def safe_rmtree(path, retries=5, delay=1.0):
    """Best-effort remove a directory tree on Windows.

    Attempts shutil.rmtree with an onerror handler. If that fails, retries
    a few times (collecting garbage between attempts) before giving up.
    Returns True if the directory was removed, False otherwise.
    """
    if not path or not os.path.exists(path):
        return True
    for attempt in range(retries):
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
            if not os.path.exists(path):
                return True
        except Exception as e:
            if attempt == retries - 1:
                print(f"Warning: Could not remove temp dir {path}: {e}")
                return False
            time.sleep(delay)
            gc.collect()
    return False

# Global list to hold .his files found in VehicleImmo folders
his_files = []

def log_message(message):
    """Print message to stdout for Electron to capture"""
    print(message, flush=True)

def is_invalid_test_vin(vin):
    """Check if a VIN is likely a placeholder/test VIN that should be excluded."""
    if not vin or len(vin) != 17:
        return True
    
    # Check for common placeholder patterns
    placeholders = [
        'AAAAAAAAAAAAAAAAA',
        '00000000000000000',
        '11111111111111111',
        'XXXXXXXXXXXXXXXXX',
        'ZZZZZZZZZZZZZZZZZ',
        'TESTVIN1234567890',
        '12345678901234567',
    ]
    
    if vin.upper() in placeholders:
        return True
    
    # Check if VIN is all the same character (like JJJJJJJJJJJJJJJJJ)
    if len(set(vin.upper())) == 1:
        return True
    
    # Check if VIN has very low character diversity (< 4 unique chars typically test data)
    unique_chars = len(set(vin.upper()))
    if unique_chars < 4:
        return True
    
    # Check for keyboard patterns or sequential characters
    test_patterns = [
        'QWERTY', 'ASDFGH', 'ZXCVBN',
        'ABCDEF', 'GHIJKL', 'MNOPQR',
        '123456', '234567', '345678'
    ]
    vin_upper = vin.upper()
    for pattern in test_patterns:
        if pattern in vin_upper:
            return True
    
    return False

def extract_vins_from_his_files(his_files_list, log_func=None):
    """
    Extract VINs from .his files found in VehicleImmo folders.
    These files contain IMMO test records.
    """
    vins_from_his = set()
    
    if not his_files_list:
        return vins_from_his
    
    if log_func:
        log_func(f"\nExtracting VINs from {len(his_files_list)} .his files (IMMO test records)...")
    
    for his_file in his_files_list:
        try:
            # Read the file content
            with open(his_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Look for 17-character VIN patterns
            vin_pattern = r'\b([A-HJ-NPR-Z0-9]{17})\b'
            matches = re.findall(vin_pattern, content)
            
            for vin in matches:
                # Skip if it's a test/placeholder VIN
                if is_invalid_test_vin(vin):
                    if log_func:
                        log_func(f"  Skipping placeholder VIN from {os.path.basename(his_file)}: {vin}")
                    continue
                
                vins_from_his.add(vin)
                if log_func:
                    log_func(f"  Found VIN in {os.path.basename(his_file)}: {vin}")
        
        except Exception as e:
            if log_func:
                log_func(f"  Error reading {his_file}: {e}")
            continue
    
    if log_func:
        log_func(f"Extracted {len(vins_from_his)} VINs from .his files\n")
    
    return vins_from_his

def detect_encoding(file_path):
    """Detect file encoding using chardet"""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
            result = chardet.detect(raw_data)
            return result.get('encoding', 'utf-8') or 'utf-8'
    except Exception:
        return 'utf-8'

def is_ipv4_or_ipv6(text):
    """Check if a text is an IPv4 or IPv6 address"""
    try:
        ip = ip_address(text)
        return isinstance(ip, (IPv4Address, IPv6Address))
    except ValueError:
        return False

def looks_like_vin(text):
    """Enhanced VIN validation"""
    if not text or len(text) != 17:
        return False
    
    # VINs should not contain I, O, Q
    if any(c in text.upper() for c in ['I', 'O', 'Q']):
        return False
    
    # VINs must be alphanumeric
    if not text.isalnum():
        return False
    
    # VINs should have a mix of letters and numbers (not all one type)
    has_letter = any(c.isalpha() for c in text)
    has_digit = any(c.isdigit() for c in text)
    if not (has_letter and has_digit):
        return False
    
    # Check if it's a test/placeholder VIN
    if is_invalid_test_vin(text):
        return False
    
    return True

def validate_vin_checksum(vin):
    """Validate VIN using check digit algorithm (US standard)"""
    try:
        vin = vin.upper()
        if len(vin) != 17:
            return False
        
        transliteration = {
            'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
            'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
            'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
            '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9
        }
        
        weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
        
        sum_value = 0
        for i, char in enumerate(vin):
            if char not in transliteration:
                return False
            sum_value += transliteration[char] * weights[i]
        
        check_digit = vin[8]
        remainder = sum_value % 11
        
        if remainder == 10:
            expected = 'X'
        else:
            expected = str(remainder)
        
        return check_digit == expected
    except Exception:
        return False

def validate_vin_manufacturer(vin):
    """Validate VIN by checking manufacturer and country codes"""
    try:
        vin_obj = Vin(vin)
        wmi = vin_obj.wmi
        if not wmi or len(wmi) < 2:
            return False
        
        country = vin_obj.country
        manufacturer = vin_obj.manufacturer
        
        if country and country.strip() and country.strip().lower() != 'unknown':
            return True
        if manufacturer and manufacturer.strip() and manufacturer.strip().lower() != 'unknown':
            return True
        
        return False
    except Exception:
        return False

def is_valid_vin(text):
    """
    Comprehensive VIN validation supporting both US checksum and international VINs
    Returns True if VIN passes either checksum validation OR manufacturer/country validation
    """
    if not looks_like_vin(text):
        return False
    
    # Try checksum validation (US standard)
    checksum_valid = validate_vin_checksum(text)
    
    # Try manufacturer/country validation (International standard)
    manufacturer_valid = validate_vin_manufacturer(text)
    
    # Accept if either validation passes
    return checksum_valid or manufacturer_valid

def get_vin_info(vin):
    """Get VIN information using dual-method approach"""
    info = {
        'VIN': vin,
        'Year': '',
        'Make': '',
        'Model': '',
        'Country': '',
        'Manufacturer': '',
        'Region': '',
        'Body': '',
        'Engine': '',
        'Plant': '',
        'Check_Digit_Valid': '',
        'Source': ''
    }
    
    # Method 1: Try NHTSA API (online, US-focused)
    try:
        result = pyvin.get(vin)
        if result and hasattr(result, '__dict__'):
            info['Year'] = str(getattr(result, 'ModelYear', ''))
            info['Make'] = str(getattr(result, 'Make', ''))
            info['Model'] = str(getattr(result, 'Model', ''))
            info['Body'] = str(getattr(result, 'BodyClass', ''))
            info['Engine'] = str(getattr(result, 'EngineModel', ''))
            info['Plant'] = str(getattr(result, 'PlantCountry', ''))
            info['Manufacturer'] = str(getattr(result, 'Manufacturer', ''))
            info['Source'] = 'NHTSA API'
            return info
    except Exception:
        pass
    
    # Method 2: Use vininfo offline decoder (international support)
    try:
        vin_obj = Vin(vin)
        info['Year'] = str(vin_obj.years) if vin_obj.years else ''
        info['Country'] = str(vin_obj.country) if vin_obj.country else ''
        info['Manufacturer'] = str(vin_obj.manufacturer) if vin_obj.manufacturer else ''
        info['Region'] = str(vin_obj.region) if vin_obj.region else ''
        info['Check_Digit_Valid'] = 'Yes' if validate_vin_checksum(vin) else 'No'
        info['Source'] = 'Offline Decoder'
        return info
    except Exception:
        pass
    
    info['Source'] = 'Unable to decode'
    return info

def extract_vins_from_text(content, source_file=''):
    """Extract valid VINs from text content"""
    vin_pattern = r'\b([A-HJ-NPR-Z0-9]{17})\b'
    matches = re.findall(vin_pattern, content)
    
    valid_vins = set()
    for match in matches:
        if is_ipv4_or_ipv6(match):
            continue
        if is_valid_vin(match):
            valid_vins.add(match)
    
    return valid_vins

def scan_directory(directory, log_func=None):
    """Scan directory for VINs in various file types"""
    all_vins = set()
    file_count = 0
    
    # Extensions to scan
    text_extensions = ['.log', '.txt', '.json', '.xml', '.csv', '.sql', '.conf', '.cfg', '.ini', '.properties']
    
    # Scan for .his files in VehicleImmo folders
    global his_files
    his_files = []
    
    if log_func:
        log_func(f"\nScanning directory: {directory}\n")
    
    for root, dirs, files in os.walk(directory):
        # Check for VehicleImmo folder and collect .his files
        if 'VehicleImmo' in root or 'vehicleimmo' in root.lower():
            for file in files:
                if file.endswith('.his'):
                    his_path = os.path.join(root, file)
                    his_files.append(his_path)
                    if log_func:
                        log_func(f"Found IMMO history file: {his_path}")
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in text_extensions:
                try:
                    encoding = detect_encoding(file_path)
                    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                        content = f.read()
                        vins = extract_vins_from_text(content, file_path)
                        if vins:
                            all_vins.update(vins)
                            file_count += 1
                            if log_func:
                                log_func(f"Found {len(vins)} VINs in: {file_path}")
                except Exception as e:
                    if log_func:
                        log_func(f"Error reading {file_path}: {e}")
            
            # Check databases
            elif file_ext == '.db':
                try:
                    vins = extract_vins_from_db(file_path, log_func)
                    if vins:
                        all_vins.update(vins)
                        file_count += 1
                except Exception as e:
                    if log_func:
                        log_func(f"Error reading database {file_path}: {e}")
    
    # Extract VINs from .his files
    if his_files:
        his_vins = extract_vins_from_his_files(his_files, log_func)
        all_vins.update(his_vins)
    
    if log_func:
        log_func(f"\nTotal: Found {len(all_vins)} unique VINs in {file_count} files\n")
    
    return all_vins

def extract_vins_from_db(db_path, log_func=None):
    """Extract VINs from SQLite database"""
    vins = set()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            try:
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                
                for row in rows:
                    for cell in row:
                        if isinstance(cell, str) and len(cell) == 17:
                            if is_valid_vin(cell):
                                vins.add(cell)
            except Exception:
                continue
        
        conn.close()
    except Exception as e:
        if log_func:
            log_func(f"Database error: {e}")
    
    return vins

def process_input(input_path, output_path, log_func=None):
    """Process input (zip or directory) and generate report
    
    Args:
        input_path: Path to ZIP file or directory to scan
        output_path: Full path to output HTML file (e.g., C:/path/report.html)
        log_func: Optional logging function
    """
    temp_dir = None
    
    try:
        # Determine if input is zip or directory
        if os.path.isfile(input_path) and input_path.lower().endswith('.zip'):
            if log_func:
                log_func(f"Extracting ZIP file: {input_path}\n")
            
            # Create temp directory for extraction
            temp_dir = tempfile.mkdtemp(prefix='kp_')
            
            with zipfile.ZipFile(input_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            scan_dir = temp_dir
        elif os.path.isdir(input_path):
            scan_dir = input_path
        else:
            raise ValueError(f"Invalid input: {input_path}")
        
        # Scan for VINs
        if log_func:
            log_func("Starting VIN extraction...\n")
        
        vins = scan_directory(scan_dir, log_func)
        
        # Get VIN information
        if log_func:
            log_func(f"\nRetrieving information for {len(vins)} VINs...\n")
        
        vin_data = []
        for i, vin in enumerate(sorted(vins), 1):
            if log_func:
                log_func(f"Processing VIN {i}/{len(vins)}: {vin}")
            
            info = get_vin_info(vin)
            vin_data.append(info)
        
        # Generate report at the specified path
        if log_func:
            log_func(f"\nGenerating report: {output_path}\n")
        
        generate_report(vin_data, output_path, input_path)
        
        if log_func:
            log_func(f"\n{'='*80}")
            log_func(f"REPORT GENERATED SUCCESSFULLY")
            log_func(f"{'='*80}")
            log_func(f"Location: {output_path}")
            log_func(f"Total VINs: {len(vins)}")
            log_func(f"{'='*80}\n")
        
        return output_path
        
    finally:
        # Cleanup temp directory
        if temp_dir and os.path.exists(temp_dir):
            if log_func:
                log_func("Cleaning up temporary files...")
            safe_rmtree(temp_dir)

def generate_report(vin_data, output_path, input_source):
    """Generate HTML report from VIN data"""
    
    # Find template file
    template_path = None
    possible_paths = [
        'report_template.html',
        os.path.join(os.path.dirname(__file__), 'report_template.html'),
        os.path.join(os.path.dirname(sys.executable), 'report_template.html'),
        os.path.join(sys._MEIPASS, 'report_template.html') if getattr(sys, 'frozen', False) else None
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            template_path = path
            break
    
    if not template_path:
        raise FileNotFoundError("report_template.html not found")
    
    # Load template
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    template = Template(template_content)
    
    # Generate report
    html_content = template.render(
        vin_lookups=vin_data,
        vins=vin_data,  # For compatibility
        total_vins=len(vin_data),
        timestamp=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        input_source=input_source,
        python_version=platform.python_version(),
        platform_info=f"{platform.system()} {platform.release()}"
    )
    
    # Write report
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='KeyProgrammer Parser - Extract VINs from Autel/XTool device dumps'
    )
    parser.add_argument('--cli', action='store_true', help='CLI mode (for Electron compatibility)')
    parser.add_argument('input', help='Input ZIP file or directory to scan')
    parser.add_argument('output', help='Output HTML file path (e.g., C:\\path\\report.html)')
    parser.add_argument('--python', help='Python executable path (for compatibility)', default=None)
    
    args = parser.parse_args()
    
    try:
        # Validate inputs
        if not os.path.exists(args.input):
            log_message(f"ERROR: Input path does not exist: {args.input}")
            sys.exit(1)
        
        # Ensure output directory exists
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            log_message(f"ERROR: Output directory does not exist: {output_dir}")
            sys.exit(1)
        
        # Process input and generate report
        report_path = process_input(args.input, args.output, log_message)
        
        log_message(f"\nSUCCESS: Report generated at {report_path}")
        sys.exit(0)
        
    except Exception as e:
        log_message(f"\nERROR: {str(e)}")
        import traceback
        log_message(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
