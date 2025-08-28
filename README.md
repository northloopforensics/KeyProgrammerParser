# KeyProgrammerParser

Currently Supports - Autel KM100, MX808, IM508 and XTool D7, AutoProPad

The tool ingests the full file system as a folder.  The first step to process the extraction is to unzip the full file system extraction to a folder on your computer. 

The next step is to create a folder where the report will be stored.

For version 1, open a command prompt where you have saved the KeyProgrammerParser.exe file and enter the command below to call the executable and point it at the file paths of the extraction folder and your report folder.

---
<b>Sample usage - KeyProgrammerParser.exe extraction_folder report_folder</b>

---
![Alt text](https://github.com/user-attachments/assets/7eaba52f-d857-4391-a04c-92b200b6956c)

---
For version 2, use the GUI to identify the extraction and report folders.  Hit Run Parser or reference the Help button.
![Alt text](https://github.com/user-attachments/assets/f0639d20-5f66-4810-9301-8b48af21fece)

---

1.  Parses log records for VINs and user details

2.  Parses vinhistory.db

3.  Copies photos of VINs taken by handset

4.  If online, will query each VIN for detailed vehicle information using the NHTSA API.

5.  If offline, will provide manufacturer information. 


Report output will include a summary of VINs found with vehicle data, results from the vinhistory.db file, each instance a VIN was found and the corresponding log file it was found in, and JPGs taken with the AUTOVIN function that get OCRd for VIN lookups.
