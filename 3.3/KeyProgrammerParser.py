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
import gzip
import xml.etree.ElementTree as ET
import html


#wificonfigstore - done
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
xtool_db = ""
xtool_data = ""
xtool_model = ""
wifi_config_store_data = pd.DataFrame()

def get_resource_path(relative_path):
    """ Get the absolute path to the resource, works for dev and for PyInstaller """
    try:
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
def copy_jpegs(jpgs_list, report_dir, progress_bar, base_directory):
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
        
    
    global vehiclehistory_db
    global vinhistory_db
    global masdas_db
    global wpa_supplicant
    global wifi_config_store_files
    print(f"Finding log files in {base_directory}")
    log_files = []
    json_files = []
    wifi_config_store_files = []
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

    wifi_config_store_files = find_wifi_config_store(base_directory)

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

def find_wifi_config_store(base_directory):
    """Find WifiConfigStore.xml files in the device extraction"""
    wifi_config_files = []
    print("Looking for WifiConfigStore.xml files...")
    for root, dirs, files in os.walk(base_directory):
        if 'misc' in root and 'wifi' in root:
            for file in files:
                if file == "WifiConfigStore.xml":
                    wifi_config_files.append(os.path.join(root, file))
                    print(f"Found WifiConfigStore.xml: {os.path.join(root, file)}")
    
    return wifi_config_files

def parse_wifi_config_store(wifi_config_files):
    """Parse WifiConfigStore.xml files to extract network data"""
    networks_data = []
    
    for config_file in wifi_config_files:
        try:
            print(f"Parsing WifiConfigStore.xml: {config_file}")
            with open(config_file, 'r', encoding='utf-8', errors='replace') as file:
                content = file.read()
                
                # Use regex to extract network blocks
                network_blocks = re.findall(r'<Network>(.*?)</Network>', content, re.DOTALL)
                
                for block in network_blocks:
                    network = {}
                    
                    # Extract SSID
                    ssid_match = re.search(r'<string name="SSID">&quot;(.*?)&quot;</string>', block)
                    if ssid_match:
                        network['SSID'] = ssid_match.group(1)
                    else:
                        continue  # Skip if no SSID found
                    
                    # Extract password
                    psk_match = re.search(r'<string name="PreSharedKey">&quot;(.*?)&quot;</string>', block)
                    network['Password'] = psk_match.group(1) if psk_match else "None"
                    
                    # Extract creation time
                    creation_time_match = re.search(r'<string name="CreationTime">time=(.*?)</string>', block)
                    network['CreationTime'] = creation_time_match.group(1) if creation_time_match else "Unknown"
                    
                    # Extract number of connections
                    num_assoc_match = re.search(r'<int name="NumAssociation" value="(\d+)" />', block)
                    network['Connections'] = num_assoc_match.group(1) if num_assoc_match else "0"
                    
                    # Extract MAC address
                    mac_match = re.search(r'<string name="RandomizedMacAddress">(.*?)</string>', block)
                    network['MACAddress'] = mac_match.group(1) if mac_match else "Unknown"
                    
                    # Extract if device has connected to this network
                    connected_match = re.search(r'<boolean name="HasEverConnected" value="(.*?)" />', block)
                    network['HasConnected'] = connected_match.group(1) if connected_match else "false"
                    
                    # Add to the list
                    networks_data.append(network)
                
                print(f"Extracted {len(networks_data)} networks from {config_file}")
                    
        except Exception as e:
            print(f"Error parsing WifiConfigStore.xml {config_file}: {e}")
    
    return pd.DataFrame(networks_data)

                
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
# Function to find log files
def find_log_files(base_directory):
    print(f"Finding log files in {base_directory}")
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
                        print(f"Error extracting {zip_path}: {e}")
        if 'database' in root:
            for file in files:
                if '._' not in file:
                    if file.endswith('vinhistory.db'):
                        global vinhistory_db
                        vinhistory_db = os.path.join(root, file)
                        print(f"VIN History DB: {vinhistory_db}")

        if 'DataBase' in root:
            for file in files:
                if file.endswith("VehicleHistory.db"):
                    global vehiclehistory_db
                    vehiclehistory_db = os.path.join(root, file)
                    print(f"Vehicle History DB: {vehiclehistory_db}")
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

        
    print(f"Found {len(log_files)} log files and {len(json_files)} JSON files")
    return log_files, json_files

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
                         vin_lookups, sources, template_path, xtool_df=None, wifi_config_store_df=None,
                         xtool_prefs_df=None, xtool_version_info=None, xtool_operating_records=None):
    
    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)
    
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
    
    # Handle XTool data
    xtool_data = []
    if xtool_df is not None and not xtool_df.empty:
        xtool_data = xtool_df.to_dict(orient='records')
    
    wifi_config_data = []
    if wifi_config_store_df is not None and not wifi_config_store_df.empty:
        wifi_config_data = wifi_config_store_df.to_dict(orient='records')
    xtool_prefs_data = []
    if xtool_prefs_df is not None and not xtool_prefs_df.empty:
        xtool_prefs_data = xtool_prefs_df.to_dict(orient='records')
    xtool_version = xtool_version_info if xtool_version_info is not None else {}
    xtool_operating = xtool_operating_records if xtool_operating_records is not None else []
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
        current_date=current_date,
        xtool_data=xtool_data,
        wifi_config_data=wifi_config_data,
    xtool_prefs=xtool_prefs_data,
    xtool_version=xtool_version,
    xtool_operating_records=xtool_operating,
    )

    # Write the rendered HTML to the report file
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
# Function to run parser
def run_parser(input_path, report_file, progress_bar):
    global jpgs, vinhistory_db, xtool_db, wifi_config_store_data, wifi_config_store_files
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
    copy_jpegs(jpgs, os.path.join(base_directory, 'Reports'), progress_bar, base_directory)
    # print("Log files found: ", len(log_files))
    
    # Find and parse XTool D7 database
    xtool_db = find_xtool_db(base_directory)
    # Also try to find and parse build.prop for device model/manufacturer info
    build_prop_path = find_build_prop(base_directory)
    if build_prop_path:
        parse_build_prop(build_prop_path)
    # Try to find profile.json under XTool profile path
    profile_path = find_profile_json(base_directory)
    profile_company = None
    profile_tel = None
    profile_email = None
    if profile_path:
        prof = parse_profile_json(profile_path)
        profile_company = prof.get('company')
        profile_tel = prof.get('tel')
        profile_email = prof.get('email')
    # Find and parse shared_prefs (Version.xml, Cocos2dxPrefsFile.xml)
    shared_prefs = find_shared_prefs(base_directory)
    xtool_version_info = None
    xtool_prefs_df = None
    if shared_prefs:
        if shared_prefs.get('Version.xml'):
            xtool_version_info = parse_version_xml(shared_prefs.get('Version.xml'))
            # also extract operating records (vehicle descriptions + VINs)
            xtool_operating_records = parse_version_operating_records(shared_prefs.get('Version.xml'))
        if shared_prefs.get('Cocos2dxPrefsFile.xml'):
            prefs_list = parse_cocos2dx_prefs_file(shared_prefs.get('Cocos2dxPrefsFile.xml'))
            try:
                xtool_prefs_df = pd.DataFrame(prefs_list)
            except Exception:
                xtool_prefs_df = pd.DataFrame()
    else:
        xtool_operating_records = []
    # Collect VINs from shared_prefs outputs so they are included in VIN lookups and reported as sources
    shared_pref_vins = []
    try:
        if xtool_operating_records:
            for rec in xtool_operating_records:
                if isinstance(rec, dict):
                    vin = rec.get('vin') or rec.get('VIN')
                    if vin and isinstance(vin, str) and len(vin) == 17:
                        shared_pref_vins.append(vin)
                        hit = f"VIN: {vin}, File: Version.xml (OperatingRecord)"
                        if hit not in hit_list:
                            hit_list.append(hit)
    except Exception:
        pass

    try:
        if xtool_prefs_df is not None and not xtool_prefs_df.empty:
            for col in ('vin', 'VIN'):
                if col in xtool_prefs_df.columns:
                    for v in xtool_prefs_df[col].dropna().astype(str).tolist():
                        if v and len(v) == 17:
                            shared_pref_vins.append(v)
                            hit = f"VIN: {v}, File: Cocos2dxPrefsFile.xml"
                            if hit not in hit_list:
                                hit_list.append(hit)
                    break
    except Exception:
        pass
    xtool_df = pd.DataFrame()
    if xtool_db:
        xtool_df = parse_xtool_db(xtool_db)
    xtool_log = find_xtool_log_file(base_directory)
    if xtool_log:
        parse_xtool_log(xtool_log)

    if wifi_config_store_files:
        wifi_config_store_data = parse_wifi_config_store(wifi_config_store_files)
    
    nickname, email, phone, address, city, state, country, detail_source, version, Product, Sub_product, dev_serial, passwrd = extract_user_data(log_files, progress_bar, total_steps)
    # Apply profile.json values as fallbacks if extract_user_data didn't find them
    try:
        if (not nickname or nickname == '') and profile_company:
            nickname = profile_company
        if (not phone or phone == '') and profile_tel:
            phone = profile_tel
        if (not email or email == '') and profile_email:
            email = profile_email
        # record profile source if used
        if profile_path and profile_company:
            src = f"Profile: {profile_path}"
            if src not in hit_list:
                hit_list.append(src)
    except Exception:
        pass
    ssid_info = SSID_parse(log_files)
    ViH_vins, ViH_df = parse_vinhistory_db(vinhistory_db, report_file, progress_bar)
    VeH_vins, VeH_df = parse_vehiclehistory_db(vehiclehistory_db, report_file, progress_bar)
    Mas_log_vins, Mas_log_df = parse_dat_log_masdas_db(masdas_db, report_file, progress_bar)
    Mas_info_vins, Mas_info_df = parse_Veh_info_masdas_db(masdas_db, report_file, progress_bar)
    wpa_wifi = parse_wpa_supplicant(wpa_supplicant)
    additional_vins = ViH_vins + VeH_vins + Mas_log_vins + Mas_info_vins
    if not xtool_df.empty and 'VIN' in xtool_df.columns:
        xtool_vins = [vin for vin in xtool_df['VIN'].tolist() if vin != "Unknown VIN" and len(vin) == 17]
        additional_vins += xtool_vins
    # include VINs extracted from shared_prefs (Version.xml operating records and Cocos2dx prefs)
    if 'shared_pref_vins' in locals() and shared_pref_vins:
        # dedupe while preserving order
        seen_v = set()
        unique_shared = []
        for v in shared_pref_vins:
            if v not in seen_v:
                seen_v.add(v)
                unique_shared.append(v)
        additional_vins += unique_shared
    vins = extract_vins(log_files, progress_bar, additional_vins)
    vin_lookups = lookup_and_report_vins(vins, json_files)
    ssid = report_SSIDs(ssid_info)
    sources = report_sources(hit_list, report_file)
    generate_html_report(nickname=nickname, email=email, phone=phone, address=address, city=city,
                        state=state, country=country, detail_source=detail_source, version=version,
                        Product=Product, Sub_product=Sub_product, dev_serial=dev_serial, 
                        passwrd=passwrd, ssid=ssid,ViH_df=ViH_df,VeH_df=VeH_df, vin_lookups=vin_lookups,
                        Mas_log_df=Mas_log_df, Mas_info_df=Mas_info_df, wpasupplicant_df=wpa_wifi,
                        sources=sources,template_path=template_path,report_file=report_file,
                        xtool_df=xtool_df, wifi_config_store_df=wifi_config_store_data,
                        xtool_prefs_df=xtool_prefs_df, xtool_version_info=xtool_version_info,
                        xtool_operating_records=xtool_operating_records)
    progress_bar.set(100)
    if zipfile.is_zipfile(input_path):
        shutil.rmtree(temp_dir)
  

def find_xtool_db(base_directory):
    """Find the XTool D7 main.db database"""
    global xtool_db
    global xtool_model
    print("Looking for XTool D7 database...")
    for root, dirs, files in os.walk(base_directory):
        if ('com.xtooltech.D7' in root or 'com.xtooltech.AutoProPadBasic' in root) and 'databases' in root:
            for file in files:
                if file == 'main.db':
                    xtool_db = os.path.join(root, file)
                    # set model based on package path
                    if 'AutoProPadBasic' in root or 'com.xtooltech.AutoProPadBasic' in root:
                        xtool_model = 'AutoProPadBasic'
                    else:
                        xtool_model = 'D7'
                    print(f"Found XTool database: {xtool_db} (model={xtool_model})")
                    return xtool_db
    
    # Also look for it directly
    potential_paths = [
        os.path.join(base_directory, "EXTRACTION_FFS 01", "EXTRACTION_FFS", "Dump", "data", "data", "com.xtooltech.D7", "databases", "main.db"),
        os.path.join(base_directory, "Dump", "data", "data", "com.xtooltech.D7", "databases", "main.db")
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            xtool_db = path
            xtool_model = 'D7'
            print(f"Found XTool D7 database: {xtool_db}")
            return xtool_db
    
    print("XTool D7 database not found")
    return None

def find_build_prop(base_directory):
    """Find a build.prop file located under a path that ends with '\\system\\build.prop'"""
    print("Looking for build.prop file...")
    for root, dirs, files in os.walk(base_directory):
        for file in files:
            if file == 'build.prop' and root.endswith(os.path.join('system')):
                candidate = os.path.join(root, file)
                print(f"Found build.prop: {candidate}")
                return candidate

    # fallback: look for any build.prop whose path contains '\\system\\build.prop'
    for root, dirs, files in os.walk(base_directory):
        for file in files:
            if file == 'build.prop' and '\\system\\build.prop' in os.path.join(root, file).replace('/', '\\'):
                candidate = os.path.join(root, file)
                print(f"Found build.prop (fallback): {candidate}")
                return candidate

    print("build.prop not found")
    return None

def parse_build_prop(build_prop_path):
    """Parse build.prop to extract device/product info"""
    global Product, Sub_product, version, dev_serial, passwrd, xtool_model
    if not build_prop_path or not os.path.exists(build_prop_path):
        return
    try:
        with open(build_prop_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Simple key=value parsing
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            if k.endswith('product.system.model') or k.endswith('product.system.name') or k == 'ro.product.system.model' or k == 'ro.system.xtool.name':
                if not Product:
                    Product = v
            if k == 'ro.build.display.id' or k == 'ro.product.system.device':
                if not Sub_product:
                    Sub_product = v
            if k == 'ro.system.build.version.release' or k == 'ro.build.version.release' or k == 'ro.build.version.sdk':
                if not version:
                    version = v
            if k == 'ro.serialno' or k == 'ro.boot.serialno' or k == 'ro.product.serial' or k == 'ro.build.host':
                if not dev_serial:
                    dev_serial = v
            if k.startswith('ro.system.xtool.device') or k == 'ro.product.system.name' or k == 'ro.system.xtool.name':
                # set xtool model identifier
                if not xtool_model:
                    xtool_model = v

        # As a fallback, if ro.product.system.brand or manufacturer indicate XTOOL, set model from known values
        if 'XTOOL' in content and not xtool_model:
            # try to grab ro.system.xtool.device
            m = re.search(r'ro.system.xtool.device=(\S+)', content)
            if m:
                xtool_model = m.group(1)

        print(f"Parsed build.prop: Product={Product}, Sub_product={Sub_product}, version={version}, dev_serial={dev_serial}, xtool_model={xtool_model}")

    except Exception as e:
        print(f"Error parsing build.prop {build_prop_path}: {e}")
def parse_xtool_db(db_path):
    """Parse the XTool D7 main.db database"""
    global xtool_data
    
    if not db_path or not os.path.exists(db_path):
        return pd.DataFrame()
    
    try:
        print(f"Parsing XTool D7 database: {db_path}")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Query both report_id and content columns
        query = """SELECT report_id, 
                content, 
                datetime(time / 1000, 'unixepoch')
                FROM diag_report"""
        cur.execute(query)
        rows = cur.fetchall()
        
        # Create a list to store extracted data
        extracted_data = []
        
        for row in rows:
            report_id, content, time = row
            print(f"Processing XTool record {report_id}")
            
            try:
                # Decompress the gzip content
                unzipped_content = gzip.decompress(content)
                
                # Try to decode as text and parse as JSON
                try:
                    json_text = unzipped_content.decode('utf-8')
                    json_data = json.loads(json_text)
                    
                    # Extract vehicle info
                    vin = json_data.get("vin", "Unknown VIN")
                    vehicle_name = json_data.get("vehicleName", "Unknown Model")
                    vehicle_year = json_data.get("vehicleYear", "Unknown Year")
                    
                    # Extract location information
                    position = json_data.get("position", {})
                    latitude = position.get("lat", "Unknown")
                    longitude = position.get("lon", "Unknown")
                    location = position.get("addr", "Unknown Location")
                    
                    # Extract diagnostic device info
                    client_info = json_data.get("clientInfo", {})
                    device_serial = client_info.get("SerialNo", "Unknown Device")
                    user_name = client_info.get("UserName", "Unknown User")
                    
                    # Extract mileage
                    mileage = json_data.get("mileage", "Unknown")
                    
                    # Add to data list
                    extracted_data.append({
                        "ReportID": report_id,
                        "Timestamp": time,
                        "VIN": vin,
                        "Year": vehicle_year,
                        "Model": vehicle_name,
                        "Mileage": mileage,
                        "Location": location,
                        "Latitude": latitude,
                        "Longitude": longitude,
                        "User": user_name,
                        "DeviceSerial": device_serial
                    })
                    
                    # Add VIN to hit list for later lookup
                    if vin and vin != "Unknown VIN" and len(vin) == 17:
                        hit_list.append(f"VIN: {vin}, File: XTool D7 main.db")
                    
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    print(f"Error decoding JSON for report {report_id}: {e}")
            
            except Exception as e:
                print(f"Error processing report {report_id}: {e}")
        
        conn.close()
        print(f"Extracted {len(extracted_data)} records from XTool D7 database")
        
        # Create DataFrame from extracted data
        xtool_data = extracted_data
        return pd.DataFrame(extracted_data)
    
    except Exception as e:
        print(f"Error connecting to XTool D7 database: {e}")
        return pd.DataFrame()
def find_xtool_log_file(base_directory):
    """Find the XTool D7 log.txt file"""
    log_file_path = None
    print("Looking for XTool D7 log.txt file...")
    
    # Try direct path based on common extraction patterns
    potential_paths = [
        os.path.join(base_directory, "data", "com.xtooltech.D7", "files", "Diagnosis", "Logs", "log.txt"),
        os.path.join(base_directory, "Dump", "data", "data", "com.xtooltech.D7", "files", "Diagnosis", "Logs", "log.txt"),
        os.path.join(base_directory, "EXTRACTION_FFS 01", "EXTRACTION_FFS", "Dump", "data", "data", "com.xtooltech.D7", "files", "Diagnosis", "Logs", "log.txt")
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            log_file_path = path
            print(f"Found XTool D7 log.txt: {log_file_path}")
            return log_file_path
    
    # If not found by direct path, search the directory structure
    for root, dirs, files in os.walk(base_directory):
        if "Logs" in root and "Diagnosis" in root and "com.xtooltech.D7" in root:
            for file in files:
                if file == "log.txt":
                    log_file_path = os.path.join(root, file)
                    print(f"Found XTool D7 log.txt: {log_file_path}")
                    return log_file_path
    
    print("XTool D7 log.txt file not found")
    return None
def parse_xtool_log(log_file_path):
    """Parse the XTool D7 log.txt file to extract device information"""
    global version, dev_serial, Product
    
    if not log_file_path or not os.path.exists(log_file_path):
        return
    try:
        print(f"Parsing XTool D7 log.txt: {log_file_path}")
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as file:
            content = file.read()

        # Extract the header section between ================= markers
        header_match = re.search(r'={5,}\n(.*?)={5,}', content, re.DOTALL)

        if header_match:
            header_content = header_match.group(1)
            # Extract required fields
            system_version_match = re.search(r'systemVersion=(\S+)', header_content)
            serial_no_match = re.search(r'serialNo=(\S+)', header_content)
            model_match = re.search(r'model=(\S+)', header_content)
            app_version_match = re.search(r'version=(\S+)', header_content)

            # Update global variables if data found
            if system_version_match and not version:
                version = system_version_match.group(1)
                print(f"XTool OS Version: {version}")

            if serial_no_match and not dev_serial:
                dev_serial = serial_no_match.group(1)
                print(f"XTool Serial Number: {dev_serial}")

            if model_match and not Product:
                Product = model_match.group(1)
                print(f"XTool Model/Product: {Product}")

            # Store app version in Sub_product if available
            if app_version_match and not Sub_product:
                Sub_product = app_version_match.group(1)
                print(f"XTool App Version: {Sub_product}")
    except Exception as e:
        print(f"Error parsing XTool D7 log.txt: {e}")

def find_shared_prefs(base_directory):
    """Locate Version.xml and Cocos2dxPrefsFile.xml under shared_prefs for AutoProPadBasic."""
    results = {}
    for root, dirs, files in os.walk(base_directory):
        # look for paths that contain com.xtooltech.AutoProPadBasic/shared_prefs
        norm = os.path.join('data', 'data', 'com.xtooltech.AutoProPadBasic', 'shared_prefs')
        try:
            if norm in os.path.join(root, ''):
                for f in files:
                    if f == 'Version.xml' or f == 'Cocos2dxPrefsFile.xml':
                        results[f] = os.path.join(root, f)
        except Exception:
            pass
    return results


def find_profile_json(base_directory):
    """Locate profile.json under XTool extraction paths.

    Expected path fragment (normalized, case-insensitive):
    data/data/com.xtooltech.AutoProPadBasic/files/Diagnosis/profile/profile.json
    """
    # Normalize the expected fragment for reliable comparison
    expected_fragment = os.path.normpath(r'data\data\com.xtooltech.AutoProPadBasic\files\Diagnosis\profile').lower()

    # First pass: look for the expected AutoProPadBasic path
    for root, dirs, files in os.walk(base_directory):
        low = os.path.normpath(root).lower()
        if expected_fragment in low:
            for f in files:
                if f.lower() == 'profile.json':
                    return os.path.join(root, f)

    # Second pass: specifically check for D7 known path
    expected_d7 = os.path.normpath(r'data\data\com.xtooltech.d7\files\Diagnosis\profile').lower()
    for root, dirs, files in os.walk(base_directory):
        low = os.path.normpath(root).lower()
    # also accept a shorter fragment that omits the leading data\data
    expected_d7_alt = os.path.normpath(r'com.xtooltech.d7\files\Diagnosis\profile').lower()
    if expected_d7 in low or expected_d7_alt in low or ('com.xtooltech.d7' in low and 'profile' in low):
            for f in files:
                if f.lower() == 'profile.json':
                    return os.path.join(root, f)

    # Third pass: generic com.xtooltech.* with a profile folder
    for root, dirs, files in os.walk(base_directory):
        low = os.path.normpath(root).lower()
        if 'com.xtooltech.' in low and 'profile' in low:
            for f in files:
                if f.lower() == 'profile.json':
                    return os.path.join(root, f)

    # Final fallback: return the first profile.json found anywhere
    for root, dirs, files in os.walk(base_directory):
        for f in files:
            if f.lower() == 'profile.json':
                return os.path.join(root, f)

    return None


def parse_profile_json(file_path):
    """Parse profile.json and return dict with keys 'company','tel','email' when present."""
    data = {}
    if not file_path or not os.path.exists(file_path):
        return data
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            j = json.load(f)
        # The file may nest useful values under keys like 'userProfile' or 'profile'
        candidates = [j]
        if isinstance(j, dict):
            for k in ('userProfile', 'profile', 'modelProfile', 'data'):
                sub = j.get(k)
                if isinstance(sub, dict):
                    candidates.append(sub)

        # helper to fetch from a dict using multiple possible keys
        def pick(d, keys):
            for kk in keys:
                if kk in d and d[kk]:
                    return d[kk]
            return None

        company_keys = ('company', 'nickName', 'nickname', 'name', 'companyName', 'contacts')
        tel_keys = ('tel', 'phone', 'telephone', 'mobile', 'phoneNumber')
        email_keys = ('email', 'mail', 'mailbox', 'emailAddress')

        company = None
        tel = None
        email_addr = None
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            if not company:
                company = pick(cand, company_keys)
            if not tel:
                tel = pick(cand, tel_keys)
            if not email_addr:
                email_addr = pick(cand, email_keys)
            # early exit if all found
            if company and tel and email_addr:
                break

        if company:
            # some values may be nested structures; coerce to string
            data['company'] = company if not isinstance(company, dict) else str(company)
        if tel:
            data['tel'] = tel if not isinstance(tel, dict) else str(tel)
        if email_addr:
            data['email'] = email_addr if not isinstance(email_addr, dict) else str(email_addr)
    except Exception:
        pass
    return data


def parse_version_xml(file_path):
    """Parse Version.xml and return a dict of values.

    Handles multiple formats observed in shared_prefs:
    - Attribute style: <int name="vciVersion" value="32773" />
    - Plist-style: <key>SomeKey</key><string>SomeValue</string>
    - nested <dict> after a <key>
    Returns a flat dictionary; nested dicts are returned as nested Python dicts.
    """
    data = {}
    if not file_path or not os.path.exists(file_path):
        return data
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Case A: nodes with a 'name' attribute (common in Android xml produced by some apps)
        for el in root.iter():
            if 'name' in el.attrib:
                key = el.attrib.get('name')
                if 'value' in el.attrib:
                    data[key] = el.attrib.get('value')
                elif el.text and el.text.strip():
                    data[key] = el.text.strip()

        # Case B: plist-style key/value pairs (<key>k</key><string>v</string>)
        # Walk the tree and detect sibling pairs under the same parent
        for parent in root.iter():
            children = list(parent)
            i = 0
            while i < len(children):
                c = children[i]
                # handle <key> followed by a value node
                if c.tag.lower() == 'key':
                    kname = c.text.strip() if c.text else ''
                    val = None
                    if i + 1 < len(children):
                        v = children[i+1]
                        t = v.tag.lower()
                        if t in ('string', 'integer'):
                            val = v.text.strip() if v.text else ''
                        elif t == 'true':
                            val = True
                        elif t == 'false':
                            val = False
                        elif t == 'dict':
                            # parse inner dict into python dict
                            inner = list(v)
                            dd = {}
                            j = 0
                            while j < len(inner):
                                if inner[j].tag.lower() == 'key':
                                    ik = inner[j].text.strip() if inner[j].text else ''
                                    iv = inner[j+1] if j+1 < len(inner) else None
                                    if iv is not None and iv.text:
                                        dd[ik] = iv.text.strip()
                                    j += 2
                                else:
                                    j += 1
                            val = dd
                        else:
                            # fallback to text content
                            val = v.text.strip() if v.text else ''
                    data[kname] = val
                    i += 2
                else:
                    i += 1

    except ET.ParseError:
        # Fallback: simple regex search for name="..." value="..."
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                txt = f.read()
                for m in re.finditer(r'name="([^"]+)"\s+value="([^"]+)"', txt):
                    data[m.group(1)] = m.group(2)
                # also try key/string pairs in text
                for m in re.finditer(r'<key>([^<]+)</key>\s*<string>([^<]+)</string>', txt):
                    data[m.group(1).strip()] = m.group(2).strip()
        except Exception:
            pass

    return data


def parse_version_operating_records(file_path):
    """Extract 'operating' or 'operating record' entries from Version.xml.

    Returns a list of dicts with keys: 'time', 'description', 'vin' when available.
    The function is defensive: it handles attribute-style entries, plist-style
    nested dicts, and plain text that contains JSON-like fragments. It looks
    for keys or text containing 'operat' (operating/操作) and then extracts
    VINs and descriptive strings.
    """
    results = []
    if not file_path or not os.path.exists(file_path):
        return results

    # helper to extract VIN from a text blob
    vin_re = re.compile(r'\b([A-HJ-NPR-Z0-9]{17})\b')

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        candidates = []
        # Collect candidate text blobs from elements that reference operating records
        for el in root.iter():
            # attribute name that may indicate operating records
            name_attr = el.attrib.get('name', '')
            text = (el.attrib.get('value') or (el.text or ''))
            if name_attr and 'oper' in name_attr.lower():
                candidates.append(text)
            # also consider any string-like element whose text contains JSON-like markers
            elif text and ('[' in text or '{' in text):
                # if the surrounding tag or name mentions oper/operation/操作, prefer it
                tag_lower = (el.tag or '').lower()
                if 'oper' in tag_lower or '操作' in (name_attr + tag_lower):
                    candidates.append(text)
                else:
                    # add as candidate but lower priority
                    candidates.append(text)

        # Fallback: read full file text and try to extract JSON arrays following OperatingRecord or 操作记录
        if not candidates:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    txt = f.read()
                    # look for JSON arrays following the words OperatingRecord or 操作
                    for m in re.finditer(r'(?:OperatingRecord|OperatingRecord\"|操作记录|操作)[^\[]*(\[.*?\])', txt, re.IGNORECASE | re.DOTALL):
                        candidates.append(m.group(1))
                    # also add any JSON array found in the file
                    for m in re.finditer(r'(\[\s*\{.*?\}\s*\])', txt, re.DOTALL):
                        candidates.append(m.group(1))
            except Exception:
                pass

        # Try to parse candidate blobs as JSON arrays or lists of JSON objects
        for cand in candidates:
            if not cand:
                continue
            s = html.unescape(cand).strip()
            # If the candidate looks like a JSON array, try to load directly
            try:
                # trim surrounding garbage
                first = s.find('[')
                last = s.rfind(']')
                if first != -1 and last != -1 and last > first:
                    jtext = s[first:last+1]
                    parsed = json.loads(jtext)
                    if isinstance(parsed, list):
                        # extend results with individual dicts
                        for item in parsed:
                            if isinstance(item, dict):
                                results.append(item)
                        # if parsed successfully, continue to next candidate
                        continue
            except Exception:
                pass

            # If not an array, try to find individual JSON objects and parse them
            try:
                objs = re.findall(r'\{.*?\}', s, re.DOTALL)
                for o in objs:
                    try:
                        obj = json.loads(o.replace('&quot;', '"'))
                        if isinstance(obj, dict):
                            results.append(obj)
                    except Exception:
                        continue
            except Exception:
                continue

    except ET.ParseError:
        # If XML can't be parsed, fall back to text search
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                txt = f.read()
                # find JSON arrays
                for m in re.finditer(r'(\[\s*\{.*?\}\s*\])', txt, re.DOTALL):
                    try:
                        parsed = json.loads(html.unescape(m.group(1)))
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, dict):
                                    results.append(item)
                    except Exception:
                        continue
        except Exception:
            pass

    # final dedupe by rep_guid if present, otherwise full dict
    seen = set()
    deduped = []
    for item in results:
        key = None
        if isinstance(item, dict):
            key = item.get('rep_guid') or json.dumps(item, sort_keys=True)
        else:
            key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped


def parse_cocos2dx_prefs_file(file_path):
    """Parse Cocos2dxPrefsFile.xml which may contain encoded JSON entries; return list of dicts."""
    results = []
    if not file_path or not os.path.exists(file_path):
        return results
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # The file may contain a single <map/> or may contain HTML-entity encoded JSON
        # Try to extract sequences like {&quot;app_ver&quot;:...}
        # Replace HTML entities
        decoded = html.unescape(content)
        # Find JSON-like objects
        objs = re.findall(r'\{[^\}]+\}', decoded)
        for obj in objs:
            try:
                # ensure valid JSON by replacing smart quotes if any
                jtext = obj
                jtext = jtext.replace("&quot;", '"')
                parsed = json.loads(jtext)
                results.append(parsed)
            except Exception:
                # skip non-json fragments
                continue
    except Exception:
        pass
    return results
    return results
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
    KeyProgrammerParser v3.2
    -------------------------
    This tool parses log files, JSON files, and databases to extract VIN and user data from: 
    - Autel KM100x 
    - Autel IM508 
    - Autel MX808
    - XTool D7
    
    Instructions:
    1. Select the input type (Zip File or Folder).  
    2. Browse to the input directory or zip file. The tool does not care about folder structure so long as files are in the correct folder.
    3. Browse to the report storage location.
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
    # Ask for a directory instead of a file
    report_dir = filedialog.askdirectory(
        title="Select folder to save report"
    )
    
    if report_dir:
        # Generate a default filename with timestamp
        default_filename = f"KeyProgrammerReport_{now.strftime('%Y%m%d_%H%M%S')}.html"
        # Combine directory and filename
        report_path = os.path.join(report_dir, default_filename)
        
        report_file_entry.delete(0, ctk.END)
        report_file_entry.insert(0, report_path)

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

def _run_cli_mode():
    """Simple CLI entrypoint: python KeyProgrammerParser.py --cli <input_dir> <report_file>"""
    import argparse

    class DummyProgress:
        def __init__(self):
            self.max = 0
        def set(self, v):
            pass
        def start(self):
            pass
        def stop(self):
            pass

    parser = argparse.ArgumentParser(description='KeyProgrammerParser CLI')
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode')
    parser.add_argument('input', nargs='?', help='Input folder or zip')
    parser.add_argument('report', nargs='?', help='Output HTML report path')
    args = parser.parse_args()

    if args.cli:
        if not args.input or not args.report:
            print('Usage: python KeyProgrammerParser.py --cli <input_path> <report_file>')
            return
        progress = DummyProgress()
        run_parser(args.input, args.report, progress)
        print('Report written to', args.report)


if __name__ == '__main__':
    # GUI setup
    ctk.set_appearance_mode("System")  # Modes: "System" (default), "Dark", "Light"
    ctk.set_default_color_theme("blue")  # Themes: "blue" (default), "green", "dark-blue", etc.

    root = ctk.CTk()
    root.title("KeyProgrammerParser v3.2")
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

    report_file_label = ctk.CTkLabel(report_frame, text="Report Output:", font=label_font)
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
