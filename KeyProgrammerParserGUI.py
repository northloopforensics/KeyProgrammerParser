import chardet
import os
import zipfile
import re
from vininfo import Vin
import pyvin
import datetime
import sqlite3
import platform
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk  
import threading  
import textwrap

################## GLOBAL VARIABLES ##################
results_list = []
hit_list = []
vinhistory_db = ""
jpgs = []
now = datetime.datetime.now()
nickname = ""
email = ""
phone = ""
city = ""
address = ""
state = ""
country = ""

################## FUNCTION SOUP ##################

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

def find_scan_jpegs(base_directory, progress_bar):
    for root, dirs, files in os.walk(base_directory):
        if 'SmartDecode' in root:
            for file in files:
                if file.endswith('.jpg'):
                    jpgs.append(os.path.join(root, file))
                    progress_bar.step(1)  # Update progress bar for each found JPEG
                    progress_bar.update()

def copy_jpegs(jpgs_list, report_dir, progress_bar):
    for jpg in jpgs_list:
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
        progress_bar.step(1)  # Update progress bar after copying each file
        progress_bar.update()

def find_log_files(base_directory):
    log_files = []
    for root, dirs, files in os.walk(base_directory):
        if 'database' in root:
            for file in files:
                if file.endswith('vinhistory.db'):
                    global vinhistory_db
                    vinhistory_db = os.path.join(root, file)
        if "DataLogging" in root:
            for file in files:
                if file.endswith('.log'):
                    log_files.append(os.path.join(root, file))
                elif file.endswith('.zip'):
                    zip_path = os.path.join(root, file)
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(root)
                            for name in zip_ref.namelist():
                                if name.endswith('.log'):
                                    log_files.append(os.path.join(root, name))
                    except Exception as e:
                        print(f"Error extracting {zip_path}: {e}")
    return log_files

def extract_vins(log_files, progress_bar):
    vins = set()
    vin_pattern = re.compile(r'\b([A-HJ-NPR-Z0-9]{17})\b')
    for log_file in log_files:
        try:
            encoding = detect_encoding(log_file)
            with open(log_file, 'r', encoding=encoding, errors='ignore') as file:
                contents = file.read()
                found_vins = vin_pattern.findall(contents)
                for vin in found_vins:
                    try:
                        if Vin(vin).verify_checksum():
                            if not vin.isdigit():
                                vins.add(vin)
                                hit_list.append(f"VIN: {vin}, File: {log_file}")
                    except Exception as e:
                        print(f"Error parsing VIN {vin}: {e}")
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
        progress_bar.step(1)  # Update progress bar after processing each file
        progress_bar.update()
    return vins
       
def extract_user_data(log_files, progress_bar, total_steps):
    global nickname, email, phone, address, city, state, country
    # Regular expressions to match the fields
    nickname_regex = re.compile(r'"nickname":"(.*?)"')
    email_regex = re.compile(r'"email":"(.*?)"')
    phone_regex = re.compile(r'"phoneNumber":"(.*?)"')
    address_regex = re.compile(r'"address":"(.*?)"')
    city_regex = re.compile(r'"city":"(.*?)"')
    state_regex = re.compile(r'"state":"(.*?)"')
    country_regex = re.compile(r'"country":"(.*?)"')

    # Loop through each log file and extract the information
    for log_file in log_files:
        try:
            encoding = detect_encoding(log_file)
            with open(log_file, 'r', encoding=encoding, errors='ignore') as file:
                contents = file.read()
                if not nickname:
                    nickname_match = nickname_regex.search(contents)
                    if nickname_match:
                        nickname = nickname_match.group(1)
                        print(f"Nickname: {nickname}")   
                if not email:
                    email_match = email_regex.search(contents)
                    if email_match:
                        email = email_match.group(1)
                        print(f"Email: {email}")   
                if not phone:
                    phone_match = phone_regex.search(contents)
                    if phone_match:
                        phone = phone_match.group(1)
                        print(f"Phone: {phone}")
                if not address:
                    address_match = address_regex.search(contents)
                    if address_match:
                        address = address_match.group(1)
                        print(f"Address: {address}")
                if not city:
                    city_match = city_regex.search(contents)
                    if city_match:
                        city = city_match.group(1)
                        print(f"City: {city}")
                if not state:
                    state_match = state_regex.search(contents)
                    if state_match:
                        state = state_match.group(1)
                        print(f"State: {state}")
                if not country:
                    country_match = country_regex.search(contents)
                    if country_match:
                        country = country_match.group(1)
                        print(f"Country: {country}")
                
                # Check if all values have been found
                if nickname and email and phone and address and city and state and country:
                    detail_source = log_file # Save the log file where the details were found   
                    break  # Exit the loop if all details are found to save time

        except Exception as e:
            print(f"Error reading {log_file}: {e}")
        
        progress_bar.step(1)  # Update progress bar after processing each file
        progress_bar.update()
    
    return nickname, email, phone, address, city, state, country, detail_source

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

def parse_vinhistory_db(vinhistory_db, report_file, progress_bar):
    if vinhistory_db == "":
        print("No vinhistory.db found.")
        with open(report_file, 'a') as f:
            f.write("********************************************************************************************************************************************************************************\n\n")
            f.write("VIN History from data/media/0/Scan/database/vinhistory.db:\n*Note DB used to OCR VIN Photos\n\n")
            f.write("No vinhistory.db found.\n\n")
    else:
        try:
            conn = sqlite3.connect(vinhistory_db)
            c = conn.cursor()
            c.execute("SELECT * FROM RECOG_RESULT")
            with open(report_file, 'a') as f:
                f.write("********************************************************************************************************************************************************************************\n\n")
                f.write("VIN History from data/media/0/Scan/database/vinhistory.db:\n*Note DB used to OCR VIN Photos\n\n")
            column_names = [description[0] for description in c.description]
            rows = c.fetchall()
            table = format_table(column_names, rows)    
            conn.close()
            with open(report_file, 'a') as f:
                f.write(table)
                f.write("\n\n")
        except Exception as e:
            print(f"Error connecting to vinhistory.db: {e}")

def make_report_header(reportfile, nickname, email, phone, address, city, state, country, detail_source):
    with open(reportfile, 'w') as f:
        f.write(f"KeyProgrammerParser Report\nDate: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n\n")
        f.write("********************************************************************************************************************************************************************************\n\n")
        f.write("User Information:\n\n")
        f.write(f"\tUsername: {nickname}\n")
        f.write(f"\tEmail: {email}\n")
        f.write(f"\tPhone: {phone}\n")
        f.write(f"\tAddress: {address}\n")
        f.write(f"\tCity: {city}\n")
        f.write(f"\tState: {state}\n")
        f.write(f"\tCountry: {country}\n\n")
        f.write(f"User data found in: {detail_source}\n\n")

def lookup_and_report_vins(vins, reportfile, progress_bar, total_steps):
    step = total_steps / (len(vins) or 1)  # Avoid division by zero

    with open(reportfile, 'a') as f:
        f.write("********************************************************************************************************************************************************************************\n\n")
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
        progress_bar.step(step)  # Update progress bar after processing each VIN
        progress_bar.update()  # Ensure the progress bar update is reflected immediately

def report_hits(reportfile):
    with open(reportfile, 'a') as f:
        f.write("********************************************************************************************************************************************************************************\n\n")
        f.write("\n\nVIN Sources:\n\n")
        for hit in hit_list:
            f.write(f"\t{hit}\n\n")

def show_help():    # To format the help text window
    help_text = textwrap.dedent("""
        Key Programmer Parser v2.0
        -------------------------------------------------------------------
        This program parses data from full file system extractions of Autel Key Programmers. 
        (Currently supports: KM100)

        Steps:
        1. Unzip the full file system extraction to a folder on your computer.
        2. Select the folder where the extraction was unzipped.
        3. Select a folder to save the report.
        4. Click Run.
        5. The report will be saved to the folder you selected.
        6. JPEGs of the scan images will be copied to the report folder.

        Artifacts parsed:
        - User data (nickname, email, phone, address, city, state, country)
        - VINs from log files
        - VINs from vinhistory.db
        - If online, VINs are run on the NHTSA API for detailed information.
        - If offline, basic VIN decoding will provide the manufacturer.

        © 2024 North Loop Consulting, LLC. All rights reserved.
    """)
    messagebox.showinfo("Help", help_text)

################## MAIN FUNCTION ##################
def run_parser(extraction_directory, report_directory, progress_bar):
    def worker():
        try:
            log_files = find_log_files(extraction_directory)
            total_files = len(log_files) + len(jpgs)  # Adjust this as needed
            if vinhistory_db:
                total_files += 1  # Add for VIN history DB processing
            total_steps = total_files * 2  # Assume 2 steps per file (e.g., finding and copying)

            progress_bar['maximum'] = total_steps
            progress_bar['value'] = 0  # Reset the progress bar

            report_file = os.path.join(report_directory, ('KeyProgrammerParser_Report_' + str(now.strftime('%Y%m%d%H%M%S')) + '.txt'))
            vins = extract_vins(log_files, progress_bar)
            nickname, email, phone, address, city, state, country, detail_source = extract_user_data(log_files, progress_bar, total_steps)
            make_report_header(report_file, nickname, email, phone, address, city, state, country, detail_source)
            lookup_and_report_vins(vins, report_file, progress_bar, total_steps)
            parse_vinhistory_db(vinhistory_db, report_file, progress_bar)
            report_hits(report_file)
            find_scan_jpegs(extraction_directory, progress_bar)
            copy_jpegs(jpgs, report_directory, progress_bar)
            progress_bar['value'] = total_steps  # Complete the progress bar

            messagebox.showinfo("Completed", f"Report was written to {report_file}\n\nFound {len(jpgs)} scanned VIN jpgs.")
        except Exception as e:
            print(f"An error occurred: {e}")
            messagebox.showerror("Error", f"An error occurred while processing. Check the console for details. {e}")

    threading.Thread(target=worker, daemon=True).start()

################## GUI SETUP ##################
def browse_directory(entry): 
    directory = filedialog.askdirectory()
    if directory:
        entry.delete(0, tk.END)
        entry.insert(0, directory)

def run_parser_gui():
    extraction_directory = extraction_entry.get()
    report_directory = report_entry.get()
    if not extraction_directory or not report_directory:
        messagebox.showwarning("Input Error", "Please provide both extraction and report directories.")
        return
    run_parser(extraction_directory, report_directory, progress_bar)

app = tk.Tk()
app.title("Key Programmer Parser v2.0 - North Loop Consulting, LLC")

# Main Frame
main_frame = tk.Frame(app, padx=10, pady=10)
main_frame.pack(fill='both', expand=True)

# Extraction Directory Frame
extraction_frame = tk.LabelFrame(main_frame, text="Extraction Directory", padx=10, pady=10)
extraction_frame.grid(row=0, column=0, padx=10, pady=10, sticky='ew')

tk.Label(extraction_frame, text="Directory:").pack(side='left', padx=5)
extraction_entry = tk.Entry(extraction_frame, width=50)
extraction_entry.pack(side='left', padx=5)
tk.Button(extraction_frame, text="Browse", command=lambda: browse_directory(extraction_entry)).pack(side='left', padx=5)

# Report Directory Frame
report_frame = tk.LabelFrame(main_frame, text="Report Directory", padx=10, pady=10)
report_frame.grid(row=1, column=0, padx=10, pady=10, sticky='ew')

tk.Label(report_frame, text="Directory:").pack(side='left', padx=5)
report_entry = tk.Entry(report_frame, width=50)
report_entry.pack(side='left', padx=5)
tk.Button(report_frame, text="Browse", command=lambda: browse_directory(report_entry)).pack(side='left', padx=5)

# Progress Bar Frame
progress_frame = tk.LabelFrame(main_frame, text="Progress", padx=10, pady=10)
progress_frame.grid(row=2, column=0, padx=10, pady=10, sticky='ew')

progress_bar = ttk.Progressbar(progress_frame, length=600, mode='determinate')
progress_bar.pack(padx=5, pady=5)

# Buttons Frame
buttons_frame = tk.Frame(main_frame, padx=10, pady=10)
buttons_frame.grid(row=3, column=0, padx=10, pady=10, sticky='ew')

tk.Button(buttons_frame, text="Run Parser",activeforeground='orange',command=run_parser_gui).pack(side='left', padx=5)
tk.Button(buttons_frame, text="Help", activeforeground='orange', command=show_help).pack(side='left', padx=5) # see show help function above, only way to format the text decently

app.mainloop()
