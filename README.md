# KeyProgrammerParser

Supports - Autel KM100

Parses full file system extractions with a focus on VIN recovery.

The tool ingests the full file system as a folder.  The first step to process the extraction is to unzip the full file system extraction to a folder on your computer. 

---
<b>Sample usage - keyprogrammerparser.exe extraction_folder report_folder</b>

---

1.  Parses log records for VINs

2.  Parses vinhistory.db

3.  Copies photos of VINs taken by handset

4.  If online, will query each VIN for detailed vehicle information using the NHTSA API.

5.  If offline, will provide manufacturer information. 


Report output will include a summary of VINs found with vehicle data, results from the vinhistory.db file, each instance a VIN was found and the corresponding log file it was found in, and JPGs taken with the AUTOVIN function that get OCRd for VIN lookups.
