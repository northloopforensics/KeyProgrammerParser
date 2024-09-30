import chardet
import os
import sys
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
import json
import logging
from tkinter.scrolledtext import ScrolledText

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
# Set logging level for chardet to WARNING to reduce verbosity
logging.getLogger('chardet').setLevel(logging.WARNING)

# Global variables
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
detail_source = ""
version = ""
Product = ""
Sub_product = ""
dev_serial = ""
passwrd = ""


# Function to detect operating system
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



# Function to find JPEG files
def find_scan_jpegs(base_directory, progress_bar):
    logging.debug(f"Finding JPEGs in {base_directory}")
    for root, dirs, files in os.walk(base_directory):
        if 'SmartDecode' in root:
            for file in files:
                if file.endswith('.jpg'):
                    jpgs.append(os.path.join(root, file))
                    progress_bar.step(1)
                    progress_bar.update()
    logging.debug(f"Found {len(jpgs)} JPEGs")

# Function to copy JPEG files
def copy_jpegs(jpgs_list, report_dir, progress_bar):
    logging.debug(f"Copying JPEGs to {report_dir}")
    for jpg in jpgs_list:
        try:
            if not os.path.exists(report_dir):
                os.makedirs(report_dir)
        except Exception as e:
            logging.error(f"Error making report directory: {e}")
        try:
            if opsys == 'Mac' or opsys == 'Linux':
                os.system(f'cp "{jpg}" "{report_dir}"')
            elif opsys == 'Windows':
                os.system(f'copy "{jpg}" "{report_dir}"')
        except Exception as e:
            logging.error(f'Error copying "{jpg}" to report directory: "{e}"')
        progress_bar.step(1)
        progress_bar.update()
    logging.debug("Finished copying JPEGs")

# Function to find log files
def find_log_files(base_directory):
    logging.debug(f"Finding log files in {base_directory}")
    log_files = []
    json_files = []
    for root, dirs, files in os.walk(base_directory):
        if "DataLogging" in root:
            for file in files:
                if file.endswith('.log'):
                    log_files.append(os.path.join(root, file))
                elif file.endswith('.zip'):
                    zip_path = os.path.join(root, file)
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            print(f"Extracting {zip_path}...")
                            zip_ref.extractall(root)
                            for name in zip_ref.namelist():
                                if name.endswith('.log'):
                                    log_files.append(os.path.join(root, name))
                    except Exception as e:
                        logging.error(f"Error extracting {zip_path}: {e}")
        if 'database' in root:
            for file in files:
                if file.endswith('vinhistory.db'):
                    global vinhistory_db
                    vinhistory_db = os.path.join(root, file)
        if 'CloudEData' in root:
            for file in files:
                if file.endswith('.json'):
                    json_path = os.path.join(root, file)
                    try:
                        with open(json_path, 'r') as json_file:
                            print(f"Parsing {json_path}...")
                            json_data = json_file.read()
                            vin = extract_json_clouddata(json_data, json_path)
                            
                            if vin != "VehicleVIN not found":
                                hit_list.append(f"VIN: {vin}, File: {json_path}")
                    except Exception as e:
                        logging.error(f"Error reading {json_path}: {e}")

        
    logging.debug(f"Found {len(log_files)} log files and {len(json_files)} JSON files")
    return log_files, json_files

# Function to extract VINs
def extract_vins(log_files, progress_bar):
    logging.debug("Extracting VINs")
    vins = set()
    vin_pattern = re.compile(r'\b([A-HJ-NPR-Z0-9]{17})\b')
    for log_file in log_files:
        try:
            encoding = 'ascii'
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
                        logging.error(f"Error parsing VIN {vin}: {e}")
        except Exception as e:
            logging.error(f"Error reading {log_file}: {e}")
        progress_bar.step(1)
        progress_bar.update()
    logging.debug(f"Extracted {len(vins)} VINs")
    return vins

# Function to extract user data
def extract_user_data(log_files, progress_bar, total_steps):
    global nickname, email, phone, address, city, state, country, detail_source
    global version, Product, Sub_product, dev_serial, passwrd  # Declare as global

    print("Extracting user data...")
    nickname_regex = re.compile(r'"nickname":"(.*?)"')
    email_regex = re.compile(r'"email":"(.*?)"')
    phone_regex = re.compile(r'"phoneNumber":"(.*?)"')
    address_regex = re.compile(r'"address":"(.*?)"')
    city_regex = re.compile(r'"city":"(.*?)"')
    state_regex = re.compile(r'"state":"(.*?)"')
    country_regex = re.compile(r'"country":"(.*?)"')
    version_regex = re.compile(r'OS:(\S+)')  # Renamed regex to avoid conflict
    product_regex = re.compile(r'Product:(\S+)')
    sub_product_regex = re.compile(r'Sub Product:(\S+)')
    dev_serial_regex = re.compile(r'SN:(\S+)')
    passwrd_regex = re.compile(r'PWD:(\S+)')




    for log_file in log_files:
        try:
            encoding = 'ascii'
            with open(log_file, 'r', encoding=encoding, errors='ignore') as file:
                contents = file.read()
                # Extract user data
                if not nickname:
                    nickname_match = nickname_regex.search(contents)
                    if nickname_match:
                        nickname = nickname_match.group(1)
                if not email:
                    email_match = email_regex.search(contents)
                    if email_match:
                        email = email_match.group(1)
                if not phone:
                    phone_match = phone_regex.search(contents)
                    if phone_match:
                        phone = phone_match.group(1)
                if not address:
                    address_match = address_regex.search(contents)
                    if address_match:
                        address = address_match.group(1)
                if not city:
                    city_match = city_regex.search(contents)
                    if city_match:
                        city = city_match.group(1)
                if not state:
                    state_match = state_regex.search(contents)
                    if state_match:
                        state = state_match.group(1)
                if not country:
                    country_match = country_regex.search(contents)
                    if country_match:
                        country = country_match.group(1)

                # Extract device data
                if not version:
                    OS_match = version_regex.search(contents)
                    if OS_match:
                        version = OS_match.group(1)
                if not Product:
                    Product_match = product_regex.search(contents)
                    if Product_match:
                        Product = Product_match.group(1)
                if not Sub_product:
                    Sub_product_match = sub_product_regex.search(contents)
                    if Sub_product_match:
                        Sub_product = Sub_product_match.group(1)
                if not dev_serial:
                    dev_serial_match = dev_serial_regex.search(contents)
                    if dev_serial_match:
                        dev_serial = dev_serial_match.group(1)
                if not passwrd:
                    passwrd_match = passwrd_regex.search(contents)
                    if passwrd_match:
                        passwrd = passwrd_match.group(1)

                # # Check if all user data is found
                # if nickname and email and phone and address and city and state and country:
                #     detail_source = log_file
                #     break
        except Exception as e:
            logging.error(f"Error reading {log_file}: {e}")
        progress_bar.step(1)
        progress_bar.update()
    print(version, Product, Sub_product, dev_serial, passwrd)
    return nickname, email, phone, address, city, state, country, detail_source, version, Product, Sub_product, dev_serial, passwrd



# Function to extract JSON data
def extract_json_clouddata(json_data, file_path):
    try:
        data = json.loads(json_data)
        vehicle_vin = data.get("VehicleVIN", None)
        if vehicle_vin:
            hit_list.append(f"VIN: {vehicle_vin}, File: {file_path}")
            return vehicle_vin
        else:
            return "VehicleVIN not found"
    except json.JSONDecodeError:
        return "Invalid JSON data"

# Function to extract SSIDs
def extract_SSIDs(log_files, progress_bar):
    logging.debug("Extracting SSIDs")
    SSIDs = set()
    SSID_pattern = re.compile(r'\b([A-HJ-NPR-Z0-9]{17})\b')
    for log_file in log_files:
        try:
            encoding = 'ascii'
            with open(log_file, 'r', encoding=encoding, errors='ignore') as file:
                contents = file.read()
                found_SSIDs = SSID_pattern.findall(contents)
                for SSID in found_SSIDs:
                    try:
                        if SSID.isdigit():
                            SSIDs.add(SSID)
                            hit_list.append(f"SSID: {SSID}, File: {log_file}")
                    except Exception as e:
                        logging.error(f"Error parsing SSID {SSID}: {e}")
        except Exception as e:
            logging.error(f"Error reading {log_file}: {e}")
        progress_bar.step(1)
        progress_bar.update()
    logging.debug(f"Extracted {len(SSIDs)} SSIDs")
    return SSIDs

# Function to format table
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

# Function to parse VIN history database
def parse_vinhistory_db(vinhistory_db, report_file, progress_bar):
    logging.debug("Parsing VIN history database")
    if vinhistory_db == "":
        logging.debug("No vinhistory.db found.")
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
            logging.error(f"Error connecting to vinhistory.db: {e}")

# Function to make report header
def make_report_header(reportfile, nickname, email, phone, address, city, state, country, detail_source, version, Product, Sub_product, dev_serial, passwrd):
    if len(nickname) == 0 and len(email) == 0 and len(phone) == 0 and len(address) == 0 and len(city) == 0 and len(state) == 0 and len(country) == 0:
        with open(reportfile, 'w') as f:
            f.write(f"KeyProgrammerParser Report\nDate: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n\n")
            f.write("********************************************************************************************************************************************************************************\n\n")
            f.write("Device Information:\n\n")
            f.write(f"\tOS: {version}\n")
            f.write(f"\tProduct: {Product}\n")
            f.write(f"\tSub Product: {Sub_product}\n")
            f.write(f"\tSerial Number: {dev_serial}\n")
            f.write(f"\tPassword: {passwrd}\n\n")
            f.write("User Information: No Registered User Found\n\n")
            f.write("********************************************************************************************************************************************************************************\n\n")
    else:
        with open(reportfile, 'w') as f:
            f.write(f"KeyProgrammerParser Report\nDate: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n\n")
            f.write("********************************************************************************************************************************************************************************\n\n")
            f.write("Device Information:\n\n")
            f.write(f"\tOS: {version}\n")
            f.write(f"\tProduct: {Product}\n")
            f.write(f"\tSub Product: {Sub_product}\n")
            f.write(f"\tSerial Number: {dev_serial}\n")
            f.write(f"\tPassword: {passwrd}\n\n")
           
     
            f.write("User Information:\n\n")
            f.write(f"\tNickname: {nickname}\n")
            f.write(f"\tEmail: {email}\n")
            f.write(f"\tPhone: {phone}\n")
            f.write(f"\tAddress: {address}\n")
            f.write(f"\tCity: {city}\n")
            f.write(f"\tState: {state}\n")
            f.write(f"\tCountry: {country}\n")
            f.write(f"\tSource File: {detail_source}\n\n")
            f.write("********************************************************************************************************************************************************************************\n\n")

# Function to lookup and report VINs
def lookup_and_report_vins(vins, reportfile):
    
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
        
def report_sources(hit_list, reportfile):
    try:
        with open(reportfile, 'a') as f:
            f.write("********************************************************************************************************************************************************************************\n\n")
            f.write("Sources:\n\n")
            for hit in hit_list:
                f.write(f"\t{hit}\n")
            f.write("\n\n")
    except Exception as e:
        logging.error(f"Error writing sources to report: {e}")
    

# Function to run parser
def run_parser(base_directory, report_file, progress_bar):
    logging.debug("Running parser")
    global jpgs, vinhistory_db
    jpgs = []
    log_files, json_files = find_log_files(base_directory)
    total_steps = len(log_files) + 100
    progress_bar.config(maximum=total_steps)
    find_scan_jpegs(base_directory, progress_bar)
    copy_jpegs(jpgs, os.path.join(base_directory, 'Reports'), progress_bar)
    print("Length of log files: ", len(log_files))
    vins = extract_vins(log_files, progress_bar)
    extract_user_data(log_files, progress_bar, total_steps)
    make_report_header(report_file, nickname, email, phone, address, city, state, country, detail_source, version, Product, Sub_product, dev_serial, passwrd)
    parse_vinhistory_db(vinhistory_db, report_file, progress_bar)
    if vins:
        lookup_and_report_vins(vins, report_file)
        report_sources(hit_list, report_file)
    else:
        with open(report_file, 'a') as f:
            f.write("No VINs found in the log files.\n\n")
    logging.debug("Finished running parser")
  

# GUI functionality
def select_directory():
    directory = filedialog.askdirectory()
    directory_entry.delete(0, tk.END)
    directory_entry.insert(0, directory)

def select_report_file():
    report_file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
    report_file_entry.delete(0, tk.END)
    report_file_entry.insert(0, report_file)

def validate_inputs(base_directory, report_file):
    if not os.path.isdir(base_directory):
        messagebox.showerror("Error", "Invalid base directory. Please select a valid directory.")
        return False
    if not report_file:
        messagebox.showerror("Error", "Please select a valid report file.")
        return False
    return True


def start_parsing():
    base_directory = directory_entry.get()
    report_file = report_file_entry.get()

    if not validate_inputs(base_directory, report_file):
        return

    progress_bar.start()

    # Define a callback for when the thread finishes
    def on_thread_complete():
        progress_bar.stop()
        messagebox.showinfo("Processing Completed", "Report written to " + report_file)
        start_button.config(state=tk.NORMAL)

    # Run the parser in a new thread
    def run_in_thread():
        try:
            run_parser(base_directory, report_file, progress_bar)
        finally:
            # Schedule the completion callback on the main thread
            root.after(0, on_thread_complete)

    # Start the thread
    parse_thread = threading.Thread(target=run_in_thread)
    parse_thread.start()

    # Disable the start button to prevent multiple clicks
    start_button.config(state=tk.DISABLED)

# Redirect stdout and stderr to the console
class ConsoleLogger:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)

    def flush(self):
        pass

# GUI setup
root = tk.Tk()
root.title("KeyProgrammerParser")

directory_label = tk.Label(root, text="Select base directory:")
directory_label.pack()
directory_entry = tk.Entry(root, width=50)
directory_entry.pack()
directory_button = tk.Button(root, text="Browse", command=select_directory)
directory_button.pack()

report_file_label = tk.Label(root, text="Select report file:")
report_file_label.pack()
report_file_entry = tk.Entry(root, width=50)
report_file_entry.pack()
report_file_button = tk.Button(root, text="Save As", command=select_report_file)
report_file_button.pack()

progress_bar = ttk.Progressbar(root, length=400, mode='determinate')
progress_bar.pack()

start_button = tk.Button(root, text="Start Parsing", command=start_parsing)
start_button.pack()

# Console window
console_label = tk.Label(root, text="Console Output:")
console_label.pack()
console_text = ScrolledText(root, height=10, width=80)
console_text.pack()

# Redirect stdout and stderr to the console
console_logger = ConsoleLogger(console_text)
sys.stdout = console_logger
sys.stderr = console_logger

root.mainloop()
 