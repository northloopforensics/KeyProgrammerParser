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
import customtkinter as ctk
import threading
import textwrap
import json
from tkinter import filedialog
from tkinter.scrolledtext import ScrolledText
import tkinter.messagebox as tkMessageBox
from ipaddress import ip_address, IPv4Address, IPv6Address
from jinja2 import Template, Environment, FileSystemLoader



#wificonfigstore
#log 'ConnectivityService' for wifi

# Global variables
hit_list = [] # this is the list of vins that will be searched on the NHTSA database
vinhistory_db = ""
vehiclehistory_db = ""
masdas_db = ""
wpa_supplicant = ""
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

def get_resource_path(relative_path):
    """ Get the absolute path to the resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Path to the template
template_path = get_resource_path('report_template.html')
# Check if the template file exists
if not os.path.exists(template_path):
    raise FileNotFoundError(f"Template file not found at {template_path}")

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
    print(f"Finding JPEGs in {base_directory}")
    for root, dirs, files in os.walk(base_directory):
        if 'SmartDecode' in root:
            for file in files:
                if file.endswith('.jpg'):
                    jpgs.append(os.path.join(root, file))   

# Function to copy JPEG files
def copy_jpegs(jpgs_list, report_dir, progress_bar):
    if len(jpgs_list) > 0:
        print(f"Copying JPEGs to {report_dir}")
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
        
    
# Function to find log files
def find_log_files(base_directory):
    global vehiclehistory_db
    global vinhistory_db
    global masdas_db
    global wpa_supplicant
    print(f"Finding log files in {base_directory}")
    log_files = []
    json_files = []
    for root, dirs, files in os.walk(base_directory):
        if "DataLogging" in root:   #seen in IM508 and KM100x
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
                        print(f"Error extracting {zip_path}: {e}")
        if "datalogging" in root:    #seen in MX808
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
                        print(f"Error extracting {zip_path}: {e}")
        if 'database' in root:  #seen in KM100x
            for file in files:
                if '._' not in file:
                    if file.endswith('vinhistory.db'):
                        vinhistory_db = os.path.join(root, file)
                        print(f"VIN History DB: {vinhistory_db}")
                    if file.endswith("VehicleHistory.db"):
                        vehiclehistory_db = os.path.join(root, file)
                        print(f"Vehicle History DB: {vehiclehistory_db}")
                    if file.endswith('masdas.db'):
                        masdas_db = os.path.join(root, file)
                        print(f"MASDAS DB: {masdas_db}")
                    

        if 'DataBase' in root:  #seen in IM608
            for file in files:
                if file.endswith("VehicleHistory.db"):
                    vehiclehistory_db = os.path.join(root, file)
                    print(f"Vehicle History DB: {vehiclehistory_db}")
                if file.endswith('vinhistory.db'):
                        vinhistory_db = os.path.join(root, file)
                        print(f"VIN History DB: {vinhistory_db}")
                if file.endswith('masdas.db'):
                        masdas_db = os.path.join(root, file)
                        print(f"MASDAS DB: {masdas_db}")
        if 'CloudEData' in root:
            for file in files:
                if file.endswith('.json'):
                    json_path = os.path.join(root, file)
                    json_files.append(json_path)
                    try:
                        with open(json_path, 'r') as json_file:
                            print(f"Parsing {json_path}...")
                            json_data = json_file.read()
                            vin = extract_json_clouddata(json_data, json_path)
                            print(f"CLOUD VIN: {vin}")
                            
                            if vin != "VehicleVIN not found":
                                hit_list.append(f"VIN: {vin}, File: {json_path}")
                    except Exception as e:
                        print(f"Error reading {json_path}: {e}")
        if "misc" in root:
            for file in files:
                if file.endswith('wpa_supplicant.conf'):
                    wpa_supplicant = os.path.join(root, file)
                    print(f"WPA Supplicant: {wpa_supplicant}")


        
    print(f"Found {len(log_files)} log files and {len(json_files)} JSON files")
    return log_files, json_files

# Function to extract VINs
def extract_vins(log_files, progress_bar, additonal_vins=None):
    print("Extracting VINs")
    vins = set()
    if additonal_vins:
        vins.update(additonal_vins)
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
                        print(f"Error parsing VIN {vin}: {e}")
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
        
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

               
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
        
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
def SSID_parse(log_files):
    ssid_info = []
    
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as file:
                entries = file.readlines()
        except UnicodeDecodeError:
            with open(log_file, 'r', encoding='latin-1') as file:
                entries = file.readlines()
        
        for entry in entries:
            if "ConnectivityService" and "CONNECTED/CONNECTED" in str(entry):
                ips = []
                filename_date = get_date_from_filename(log_file=log_file)
                date_time, ssid, ip_addresses, ipv6_addresses = parse_log_for_SSID(entry)
                date_time = filename_date + '-' + date_time
                for ip, classification in ip_addresses.items():
                    if classification == 'Public':
                        ips.append(f"{ip}: {classification}")
                    
                for ip, classification in ipv6_addresses.items():
                    if classification == 'Public':
                        ips.append(f"{ip}: {classification}")
                
                if ssid != 'Not found' and ips != []:
                    ssid_info.append((date_time, ssid, ips))
                        
    # Sort ssid_info by date_time
    ssid_info.sort(key=lambda x: x[0])
    ssid_info = list(set((date_time, ssid, tuple(ips)) for date_time, ssid, ips in ssid_info))    # remove duplicates
    ssid_info = [(date_time, ssid, list(ips)) for date_time, ssid, ips in ssid_info] # Convert set to list

    return ssid_info
                                                              
                
def get_date_from_filename(log_file):
    filename = os.path.basename(log_file)
    date_parts = filename.split('_')
    if len(date_parts) > 1:
        date = date_parts[1]
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        
        good_date = f"{year}"
        return good_date
    else:
        return "Unknown Date"
    

def parse_log_for_SSID(log_entry):
    # Regular expressions
    date_time_pattern = r'\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}'
    ssid_pattern = r'SSID: "([^"]+)"'
    ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
    ipv6_pattern = r'\b(?:[a-fA-F0-9]{1,4}:){7}[a-fA-F0-9]{1,4}\b'

    # Extract date and time
    date_time_match = re.search(date_time_pattern, log_entry)
    date_time = date_time_match.group(0) if date_time_match else "Not found"

    # Extract SSID
    ssid_match = re.search(ssid_pattern, log_entry)
    ssid = ssid_match.group(1) if ssid_match else "Not found"

    # Extract IP addresses
    ip_matches = re.findall(ip_pattern, log_entry)
    ipv6_matches = re.findall(ipv6_pattern, log_entry)
    ip_addresses = {ip: classify_ip(ip) for ip in ip_matches}
    ipv6_addresses = {ip: classify_ip(ip) for ip in ipv6_matches}
    return  date_time,ssid,ip_addresses,ipv6_addresses

def report_SSIDs(ssid_info):
    # Convert the SSID info into a pandas DataFrame
    columns = ["Connection Date", "SSID", "DNS IPs"]
    data = []

    for date_time, ssid, ips in ssid_info:
        data.append([date_time, ssid, ", ".join(ips)])
        # print(f"Connection Date: {date_time}, SSID: {ssid}, DNS IPs: {', '.join(ips)}")

    df = pd.DataFrame(data, columns=columns)
    return df
# Classify IP addresses as public or private
def classify_ip(ip):
    try:
        ip_obj = ip_address(ip)
        if ip_obj.is_private:
            return "Private"
        else:
            return "Public"
    except ValueError:
        return "Invalid"


def format_table(column_names, results):
    results = [[str(value) if value is not None else '' for value in row] for row in results]
    col_widths = [max(len(str(value)) for value in col) for col in zip(*results, column_names)]
    format_str = ' | '.join(f"{{:<{width}}}" for width in col_widths)
    header = format_str.format(*column_names)
    separator = '-+-'.join('-' * width for width in col_widths)
    rows = [format_str.format(*row) for row in results]
    table = '\n'.join([header, separator] + rows)
    
    return table

# Function to parse VIN history database
def parse_vinhistory_db(vinhistory_db, report_file, progress_bar):
    df = pd.DataFrame()  
    db_vins = []

    if not vinhistory_db:
        return db_vins, df
    else:
        try:
            conn = sqlite3.connect(vinhistory_db)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='RECOG_RESULT'")
            if not c.fetchone():
                print(f"vinhistory.db not located in data set.")
                return db_vins, df

            c.execute("SELECT * FROM RECOG_RESULT")
            column_names = [description[0] for description in c.description]
            rows = c.fetchall()
            table = format_table(column_names, rows)
            # Keep track of VINs
            unique_vin_codes = [str(row[0]) for row in rows if row[0] and len(str(row[0])) == 17]
            for vin in unique_vin_codes:
                hit_list.append(f"VIN: {vin}, File: {vinhistory_db}")
                db_vins.append(vin)
            conn.close()

            # Convert query results into a DataFrame
            df = pd.DataFrame(rows, columns=column_names)

            return db_vins, df

        except sqlite3.DatabaseError as e:
            print(f"Error {vinhistory_db}: {e}")
            print(f"Error connecting to vinhistory.db: {e}")
            return db_vins, df
        except Exception as e:
            print(f"Error connecting to vinhistory.db: {e}")
            return db_vins, df

# Function to parse vehicle history database
def parse_vehiclehistory_db(vehiclehistory_db, report_file, progress_bar):
    db_vins = []
    df = pd.DataFrame()

    if not vehiclehistory_db:
        return db_vins, df
    else:
        try:
            conn = sqlite3.connect(vehiclehistory_db)
            c = conn.cursor()
            c.execute("""
                SELECT 
                    DISTINCT vin_code, 
                    year, 
                    make, 
                    model, 
                    datetime(last_use_time / 1000, 'unixepoch') as last_use_time
                FROM 
                    tb_customer_vehicle;
            """)
            

            column_names = [description[0] for description in c.description]
            rows = c.fetchall()

            # Keep track of VINs
            unique_vin_codes = [str(row[0]) for row in rows if row[0] and len(str(row[0])) == 17]
            for vin in unique_vin_codes:
                hit_list.append(f"VIN: {vin}, File: {vehiclehistory_db}")
                db_vins.append(vin)
            conn.close()

            df = pd.DataFrame(rows, columns=column_names)

        except sqlite3.DatabaseError as e:
            # print(f"Error {vehiclehistory_db}: {e}")     
            print(f"Not connecting to VehicleHistory.db: {e}")
            pass
        except Exception as e:
            print(f"VehicleHistory.db not found in data set.")

    # Return both the list of VINs as before, and the newly created DataFrame
    return db_vins, df

def parse_Veh_info_masdas_db(masdas_db, report_file, progress_bar):
    # parse VEHICHLE_INFO_3 table of masdas.db
    db_vins = []
    df = pd.DataFrame()

    if not masdas_db:
        return db_vins, df
    else:
        try:
            conn = sqlite3.connect(masdas_db)
            c = conn.cursor()
            c.execute("""
                SELECT 
                    DISTINCT VIN,
                    MAKE,
                    MODEL,
                    YEAR,
                    datetime(DATETIME / 1000, 'unixepoch') as DATE
                FROM 
                    VEHICLE_INFO_3
            """)
            

            column_names = [description[0] for description in c.description]
            rows = c.fetchall()

            # Keep track of VINs
            unique_vin_codes = [str(row[0]) for row in rows if row[0] and len(str(row[0])) == 17]
            for vin in unique_vin_codes:
                hit_list.append(f"VIN: {vin}, File: {masdas_db}")
                db_vins.append(vin)
            conn.close()

            df = pd.DataFrame(rows, columns=column_names)

        except sqlite3.DatabaseError as e:
            print(f"Error {masdas_db}: {e}")     
            print(f"Error connecting to MASDAS.db: {e}")
        except Exception as e:
            print(f"Error connecting to MASDAS.db: {e}")

    # Return both the list of VINs as before, and the newly created DataFrame
    return db_vins, df

def parse_dat_log_masdas_db(masdas_db, report_file, progress_bar):
    # parse DATA_DATALOGGING_TABLE_VERSION_8 table of masdas.db
    db_vins = []
    df = pd.DataFrame()

    if not masdas_db:
        return db_vins, df
    else:
        try:
            conn = sqlite3.connect(masdas_db)
            c = conn.cursor()
            c.execute("""
                SELECT 
                    VIN,
                    CAR,
                    MODEL,
                    YEAR,
                    datetime(CREATE_TIME / 1000, 'unixepoch') as DATE
                FROM 
                    DATA_DATALOGGING_TABLE_VERSION_8
            """)
            

            column_names = [description[0] for description in c.description]
            rows = c.fetchall()

            # Keep track of VINs
            unique_vin_codes = [str(row[0]) for row in rows if row[0] and len(str(row[0])) == 17]
            for vin in unique_vin_codes:
                hit_list.append(f"VIN: {vin}, File: {masdas_db}")
                db_vins.append(vin)
            conn.close()

            df = pd.DataFrame(rows, columns=column_names)

        except sqlite3.DatabaseError as e:
            # print(f"Error {masdas_db}: {e}")     
            print(f"Not connecting to MASDAS.db: {e}")
            
        except Exception as e:
            print(f"MASDAS.db not found in data set.")

    # Return both the list of VINs as before, and the newly created DataFrame
    return db_vins, df

def parse_wpa_supplicant(wpa_supplicant):

    if not wpa_supplicant:
        # Return an empty DataFrame if path is invalid
        return pd.DataFrame(columns=["SSID", "PSK"])
    try:
        with open(wpa_supplicant, 'r') as file:
            file_content = file.read()
            networks = re.findall(r'network=\{(.*?)\}', file_content, re.DOTALL)
            parsed_data = []

            for network in networks:
                ssid_match = re.search(r'ssid="(.*?)"', network)
                psk_match = re.search(r'psk="(.*?)"', network)

                if ssid_match:
                    ssid = ssid_match.group(1)
                    psk = psk_match.group(1) if psk_match else None
                    parsed_data.append({"SSID": ssid, "PSK": psk})
            # print("Parsed Data: ", parsed_data)
            # print("DF: ", pd.DataFrame(parsed_data))
            return pd.DataFrame(parsed_data)
                   
    except Exception as e:
        print(f"Error reading {wpa_supplicant}: {e}")
        return pd.DataFrame(columns=["SSID", "PSK"])

# Function to lookup and report VINs
def lookup_and_report_vins(vins, json_files):
    # Extract VINs from JSON files
    for json_file in json_files:
        try:
            with open(json_file, 'r') as file:
                json_data = file.read()
                vin = extract_json_clouddata(json_data, json_file)
                if vin != "VehicleVIN not found":
                    vins.add(vin)
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    # Prepare a list to store VIN info for DataFrame
    vin_data = []

    print(f"Extracted {len(vins)} VINs")

    for vin in vins:
        try:
            vehicle = pyvin.VIN(vin)
            # Save to file
            
            # Keep track for DataFrame
            vin_data.append({
                "VIN": vin,
                "Make": vehicle.Make,
                "Model": vehicle.Model,
                "Trim": vehicle.Trim,
                "Year": vehicle.ModelYear,
                "Type": vehicle.VehicleType
            })

        except Exception as e:
            # If PyVIN fails, fallback to vininfo
            vin_info = Vin(vin)

            # print(f"VIN: {vin} Annot: {vin_info.annotate()}")

            # Keep track for DataFrame with minimal data
            vin_data.append({
                "VIN": vin,
                "Make": "N/A",
                "Model": "N/A",
                "Trim": "N/A",
                "Year": "N/A",
                "Type": "N/A",
                "Annotation": vin_info.annotate()
            })
    # Convert vin_data list into a DataFrame and return it
    df = pd.DataFrame(vin_data)
    return df
        
def report_sources(hit_list, reportfile):
    try:
        # Remove duplicates and sort the hit list
        set_hit_list = set(hit_list)
        sorted_hit_list = sorted(set_hit_list)
        
        # Create a DataFrame from the sorted hit list
        df = pd.DataFrame(sorted_hit_list, columns=["Source"])
        
        
        return df
    except Exception as e:
        print("Report Sources Error:", e)
        return pd.DataFrame()  # Return an empty DataFrame in case of error

def generate_html_report(report_file, nickname, email, phone, address, city, state, country, 
                         detail_source, version, Product, Sub_product, dev_serial, passwrd, ssid,
                         ViH_df, VeH_df, Mas_log_df, Mas_info_df, wpasupplicant_df,
                         vin_lookups, sources, template_path):
    
    # Ensure the template path is correct
    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)
    
    # Load the template
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)

    # Convert DataFrames to dictionaries
    ViH_data = ViH_df.to_dict(orient='records')
    VeH_data = VeH_df.to_dict(orient='records')
    Mas_log_data = Mas_log_df.to_dict(orient='records')
    Mas_info_data = Mas_info_df.to_dict(orient='records')
    wpa_supplicant_data = wpasupplicant_df.to_dict(orient='records')
    vin_lookups_data = vin_lookups.to_dict(orient='records')
    ssid_data = ssid.to_dict(orient='records')
    
    # Ensure sources is a DataFrame and convert to list
    if isinstance(sources, pd.DataFrame):
        sources_data = sources['Source'].tolist()
    else:
        sources_data = []

    current_date = now.strftime('%Y-%m-%d %H:%M:%S')

    # Render the template with the data
    html_content = template.render(
        nickname=nickname,
        email=email,
        phone=phone,
        address=address,
        city=city,
        state=state,
        country=country,
        detail_source=detail_source,
        version=version,
        Product=Product,
        Sub_product=Sub_product,
        dev_serial=dev_serial,
        passwrd=passwrd,
        ssid=ssid_data,
        ViH_data=ViH_data,
        VeH_data=VeH_data,
        Mas_log_data=Mas_log_data,
        Mas_info_data=Mas_info_data,
        wpa_supplicant_data=wpa_supplicant_data,
        vin_lookups=vin_lookups_data,
        sources=sources_data,
        current_date=current_date
    )

    # Write the rendered HTML to the report file
    with open(report_file, 'w') as f:
        f.write(html_content)
# Function to run parser
def run_parser(input_path, report_file, progress_bar):
    global jpgs, vinhistory_db
    jpgs = []

    # Check if the input path is a zip file or a directory
    if zipfile.is_zipfile(input_path):
        # Create a temporary directory to extract the zip file
        temp_dir = tempfile.mkdtemp()
        try:
            print(f"Extracting {input_path} to {temp_dir}")
            with zipfile.ZipFile(input_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            base_directory = temp_dir
        except Exception as e:
            print(f"Error extracting {input_path}: {e}")
            shutil.rmtree(temp_dir)
            return
    else:
        base_directory = input_path

    log_files, json_files = find_log_files(base_directory)
    total_steps = len(log_files)
    progress_bar.set(0)  # Reset to 0 before starting
    progress_bar.max = total_steps  # Set the max directly
    # progress_bar.configure(maximum=total_steps)
    find_scan_jpegs(base_directory, progress_bar)
    copy_jpegs(jpgs, os.path.join(base_directory, 'Reports'), progress_bar)
    # print("Log files found: ", len(log_files))
    
    nickname, email, phone, address, city, state, country, detail_source, version, Product, Sub_product, dev_serial, passwrd = extract_user_data(log_files, progress_bar, total_steps)
    ssid_info = SSID_parse(log_files)
    ViH_vins, ViH_df = parse_vinhistory_db(vinhistory_db, report_file, progress_bar)
    VeH_vins, VeH_df = parse_vehiclehistory_db(vehiclehistory_db, report_file, progress_bar)
    Mas_log_vins, Mas_log_df = parse_dat_log_masdas_db(masdas_db, report_file, progress_bar)
    Mas_info_vins, Mas_info_df = parse_Veh_info_masdas_db(masdas_db, report_file, progress_bar)
    wpa_wifi = parse_wpa_supplicant(wpa_supplicant)
    additional_vins = ViH_vins + VeH_vins + Mas_log_vins + Mas_info_vins
    vins = extract_vins(log_files, progress_bar, additional_vins)
    vin_lookups = lookup_and_report_vins(vins, json_files)
    ssid = report_SSIDs(ssid_info)
    sources = report_sources(hit_list, report_file)
    generate_html_report(nickname=nickname, email=email, phone=phone, address=address, city=city,
                        state=state, country=country, detail_source=detail_source, version=version,
                        Product=Product, Sub_product=Sub_product, dev_serial=dev_serial, 
                        passwrd=passwrd, ssid=ssid,ViH_df=ViH_df,VeH_df=VeH_df, vin_lookups=vin_lookups,
                        Mas_log_df=Mas_log_df, Mas_info_df=Mas_info_df, wpasupplicant_df=wpa_wifi,
                        sources=sources,template_path=template_path,report_file=report_file)
    progress_bar.set(100)
    if zipfile.is_zipfile(input_path):
        shutil.rmtree(temp_dir)
  


# Function to run parser in a thread
def run_in_thread(base_directory, report_file, progress_bar):
    try:
        run_parser(base_directory, report_file, progress_bar)
    finally:
        root.after(0, lambda: on_thread_complete(report_file))

# Function to handle thread completion
def on_thread_complete(report_file):
    progress_bar.stop()
    tkMessageBox.showinfo("Processing Completed", "Report written to " + report_file)
    start_button.configure(state=ctk.NORMAL)

# GUI functionality
def show_help():
    help_text = textwrap.dedent("""
    KeyProgrammerParser v3.1
    -------------------------
    This tool parses log files, JSON files, and databases to extract VIN and user data from: 
    - Autel KM100x 
    - Autel IM508 
    - Autel MX808
    
    Instructions:
    1. Select the input type (Zip File or Folder).  
    2. Browse to the input directory or zip file. The tool does not care about folder structure so long as files are in the correct folder.
    3. Browse to the report file location.
    4. Click the "Start Parsing" button to begin.
    
    Results:
    - VINs extracted from log files and JSON files. If online,lookup details are collected from the US NHTSA VIN database.
    - User data is extracted from log files.
    - vinhistory.db database is related to photo OCR services found on some units.
    - SSID connections extracted from log files and databases. If found, DNS IPs may help determine ISP usage. IP lookup will help determine service providers.
    - Sources of VINs and other data extracted are listed for reference.

    Note: Normal forensic practices should be followed when handling evidence. Verify timestamps and integrity of the data.
    """)
    tkMessageBox.showinfo("Help", help_text)
    
def select_directory():
    if input_type.get() == "zip":
        input_path = filedialog.askopenfilename(
            title="Select Zip File",
            filetypes=[("Zip Files", "*.zip")]
        )
    else:
        input_path = filedialog.askdirectory(
            title="Select Directory"
        )
    directory_entry.delete(0, ctk.END)
    directory_entry.insert(0, input_path)

def select_report_file():
    report_file = filedialog.asksaveasfilename(
        defaultextension=".html",
        filetypes=[("HTML files", "*.html")]
    )
    report_file_entry.delete(0, ctk.END)
    report_file_entry.insert(0, report_file)

def validate_inputs(base_directory, report_file):
    if not base_directory or not os.path.exists(base_directory):
        tkMessageBox.showerror("Error", "Invalid base directory. Please select a valid directory or zip file.")
        return False
    if not report_file:
        tkMessageBox.showerror("Error", "Invalid report file. Please select a valid report file.")
        return False
    return True

def start_parsing():
    base_directory = directory_entry.get()
    report_file = report_file_entry.get()
    if validate_inputs(base_directory, report_file):
        progress_bar.set(0)
        progress_bar.start()
        # Start the parsing in a new thread
        threading.Thread(target=run_in_thread, args=(base_directory, report_file, progress_bar)).start()
        start_button.configure(state=ctk.DISABLED)

# Redirect stdout and stderr to the console
class ConsoleLogger:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(ctk.END, message)
        self.text_widget.see(ctk.END)

    def flush(self):
        pass

# GUI setup
ctk.set_appearance_mode("System")  # Modes: "System" (default), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (default), "green", "dark-blue", etc.

root = ctk.CTk()
root.title("KeyProgrammerParser v3.1")
root.geometry("840x620")

# Styling
label_font = ('Arial', 12)

## Frame for input type selection
input_type_frame = ctk.CTkFrame(root)
input_type_frame.pack(pady=10)

input_type_label = ctk.CTkLabel(input_type_frame, text="Select input type:", font=label_font)
input_type_label.pack(side=ctk.LEFT)

input_type = ctk.StringVar(value="zip")
zip_radio = ctk.CTkRadioButton(input_type_frame, text="Zip File", variable=input_type, value="zip")
zip_radio.pack(side=ctk.LEFT, padx=5)
folder_radio = ctk.CTkRadioButton(input_type_frame, text="Folder", variable=input_type, value="folder")
folder_radio.pack(side=ctk.LEFT, padx=5)

# Frame for directory selection
directory_frame = ctk.CTkFrame(root)
directory_frame.pack(pady=10)

directory_label = ctk.CTkLabel(directory_frame, text="Path to Input:", font=label_font)
directory_label.pack(side=ctk.LEFT)

directory_entry = ctk.CTkEntry(directory_frame, width=400)
directory_entry.pack(side=ctk.LEFT, padx=5)

directory_button = ctk.CTkButton(directory_frame, text="Browse", command=select_directory)
directory_button.pack(side=ctk.LEFT)

# Frame for report file selection
report_frame = ctk.CTkFrame(root)
report_frame.pack(pady=10)

report_file_label = ctk.CTkLabel(report_frame, text="Select report file:", font=label_font)
report_file_label.pack(side=ctk.LEFT)

report_file_entry = ctk.CTkEntry(report_frame, width=400)
report_file_entry.pack(side=ctk.LEFT, padx=5)

report_file_button = ctk.CTkButton(report_frame, text="Browse", command=select_report_file)
report_file_button.pack(side=ctk.LEFT)

# Progress bar
progress_bar = ctk.CTkProgressBar(root, width=700, mode='determinate')  # Set mode to 'determinate'
progress_bar.pack(pady=10)  # Ensure it's visible
progress_bar.set(0)  # Reset to 0 before starting


# Start button
start_button = ctk.CTkButton(root, text="Start Parsing", command=start_parsing)
start_button.pack(pady=10)

# Help button

help_frame = ctk.CTkFrame(root)
help_frame.pack(side=ctk.BOTTOM, anchor=ctk.E, pady=5, padx=5)

# Create the help button with smaller font and less prominent color
help_button = ctk.CTkButton(help_frame, text="?", command=show_help, font=("Arial", 10), fg_color="gray")
help_button.pack()

# Console output
console_frame = ctk.CTkFrame(root)
console_frame.pack(pady=1)

console_label = ctk.CTkLabel(console_frame, text="", font=label_font)
console_label.pack()

console_text = ScrolledText(console_frame, height=50, width=200, bg='#ffffff', font=('Arial', 10))
console_text.pack()

# Redirect stdout and stderr to the console
console_logger = ConsoleLogger(console_text)
sys.stdout = console_logger
sys.stderr = console_logger

# Start the main loop
root.mainloop()
