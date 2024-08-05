import chardet
import os
import zipfile
import re
from vininfo import Vin
import pyvin
import datetime
import sqlite3
import platform
import argparse

################## GLOBAL VARIABLES ##################
results_list = []
hit_list = []
vinhistory_db = []
jpgs = []
now = datetime.datetime.now()
################## FUNCTION VILLAGE ##################
def detect_operating_system():
    os_name = os.name
    if os_name == 'posix':
        system_name = platform.system()
        if system_name == 'Darwin':
            return 'Mac'
        else:
            return 'Linux'
    elif os_name == 'nt':
        return 'Windows'
    else:
        return 'Unknown'
opsys = detect_operating_system()

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read()
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    return encoding

def find_scan_jpegs(base_directory):
    for root, dirs, files in os.walk(base_directory):
        if 'SmartDecode' in root:
            for file in files:
                if file.endswith('.jpg'):
                    jpgs.append(os.path.join(root, file))

def copy_jpegs(jpgs_list, report_dir):
    for jpg in jpgs_list:
        # print(f"Copying {jpg} to {report_dir}")
        try:
            if not os.path.exists(report_dir):
                os.makedirs(report_dir)
        except Exception as e:
            print(f"Error making report directory: {e}")
        try:
            if opsys == 'Mac' or opsys == 'Linux':
                os.system(f'cp "{jpg}" "{report_dir}"') 
            elif opsys == 'Windows':
                os.system(f'copy "{jpg}" "{report_dir}"')
        except Exception as e:
            print(f'Error copying "{jpg}" to report directory: "{e}"')

def find_log_files(base_directory):
    log_files = []
    for root, dirs, files in os.walk(base_directory):
        if 'database' in root:
            for file in files:
                if file.endswith('vinhistory.db'):
                    vinhistory_db.append(os.path.join(root, file))
        if "DataLogging" in root:
            for file in files:
                if file.endswith('.log'):
                    log_files.append(os.path.join(root, file))
                elif file.endswith('.zip'):
                    zip_path = os.path.join(root, file)
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(root)
                        for name in zip_ref.namelist():
                            if name.endswith('.log'):
                                log_files.append(os.path.join(root, name))
    return log_files

def extract_vins(log_files):
    vin_pattern = re.compile(r'\b[A-HJ-NPR-Z0-9]{17}\b')
    vins = set()
    for log_file in log_files:
        try:
            encoding = detect_encoding(log_file)
            with open(log_file, 'r', encoding=encoding, errors='ignore') as file:
                contents = file.read()
                found_vins = vin_pattern.findall(contents)
                for vin in found_vins:
                    try:
                        if Vin(vin).verify_checksum() == True:
                            vins.add(vin)
                            hit_list.append(f"VIN: {vin}, File: {log_file}")
                    except Exception as e:
                        print(f"Error parsing VIN {vin}: {e}")
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
    return vins

def format_table(column_names, results):
    results = [[item if item is not None else '' for item in row] for row in results]
    column_widths = [max(len(str(item)) for item in column) for column in zip(*results, column_names)]
    format_str = ' | '.join(f'{{:<{width}}}' for width in column_widths)
    table = format_str.format(*column_names)
    table += '\n'
    table += '-+-'.join('-' * width for width in column_widths)
    for row in results:
        table += '\n' + format_str.format(*row)
    return table

def parse_vinhistory_db(vinhistory_db, report_file):
    conn = sqlite3.connect(vinhistory_db[0])
    c = conn.cursor()
    c.execute("SELECT * FROM RECOG_RESULT")
    with open(report_file, 'a') as f:
        f.write("****************************************************************************************\n\n")
        f.write("VIN History from data/media/0/Scan/database/vinhistory.db:\n*Note DB used to OCR VIN Photos\n\n")
    column_names = [description[0] for description in c.description]
    rows = c.fetchall()
    table = format_table(column_names, rows)    
    conn.close()
    with open(report_file, 'a') as f:
        f.write(table)
        f.write("\n\n")

def make_report_header(reportfile):
    with open(reportfile, 'w') as f:
        f.write(f"KeyProgrammerParser Report\nDate: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n\n")

def lookup_and_report_vins(vins, reportfile):
    with open(reportfile, 'a') as f:
        f.write("****************************************************************************************\n\n")
        f.write("VIN Summary:\n\n")
    for vin in vins:
        try:
            vehicle = pyvin.VIN(vin)
            with open(reportfile, 'a') as f:
                f.write(f"\tVIN: {vin} Make: {vehicle.Make} Model: {vehicle.Model} {vehicle.Trim} Year: {vehicle.ModelYear} Type: {vehicle.VehicleType}\n\n")
            print(f"VIN: {vin} Make: {vehicle.Make} Model: {vehicle.Model} {vehicle.Trim} Year: {vehicle.ModelYear} Type: {vehicle.VehicleType}")
        except Exception as e:
            vin_info = Vin(vin)
            with open(reportfile, 'a') as f:
                f.write(f"\tVIN: {vin} Annot: {vin_info.annotate()}\n")
            print(f"Vin: {vin} annot: {vin_info.annotate()}")

def report_hits(reportfile):
    with open(reportfile, 'a') as f:
        f.write("****************************************************************************************\n\n")
        f.write("\n\nVIN Sources:\n\n")
        for hit in hit_list:
            f.write(f"\t{hit}\n\n")

def main():
    parser = argparse.ArgumentParser(description='''KeyProgrammerParser (Autel KM100). This tool parses the Autel Key Programmer (KM100) vinhistory.db file, 
                        extracts VINs from log files, and copies of photographs taken to scan VINs. To create the extraction directory,
                        unzip the full file system extraction from the Autel Key Programmer (KM100) to a directory on your computer. 
                        If working on a Mac or Linux system, you may need to change the permissions on the extraction files to read/write. 
                        It is unnecesary to change permissions if working on a Windows system. The report directory is where the report 
                        and recovered photographs will be placed.   ''')
    parser.add_argument('extraction_directory', type=str, help='The directory containing full file system extraction')
    parser.add_argument('report_directory', type=str, help='The directory to output reports and pictures')
    
    args = parser.parse_args()

    extraction_directory = args.extraction_directory
    report_directory = args.report_directory
    report_file = os.path.join(report_directory, ('KeyProgrammerParser_Report_' + str(now.strftime('%Y%m%d%H%M%S')) + '.txt'))

    log_files = find_log_files(extraction_directory)
    print(" ")
    print("Searching for log files...")
    make_report_header(report_file)
    print(f"Found {len(log_files)} log files.")
    print(" ")
    print("Searching for VINs. Lots to Unzip. Patience please...")
    vins = extract_vins(log_files)
    lookup_and_report_vins(vins, report_file)
    print(" ")
    print("Parsing vinhistory.db...")
    parse_vinhistory_db(vinhistory_db, report_file)
    print(" ")
    report_hits(report_file)
    print("Searching for scan jpgs...")
    find_scan_jpegs(extraction_directory)
    print(f"Found {len(jpgs)} scan jpgs.")
    print("Copying scan jpgs to report folder...")
    copy_jpegs(jpgs, report_directory)
    print(" ")
    print(f"Report written to {report_file}")

if __name__ == "__main__":
    main()
