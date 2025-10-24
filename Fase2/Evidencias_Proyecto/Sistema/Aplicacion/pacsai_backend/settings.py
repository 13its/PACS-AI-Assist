# settings.py
import os

# URL base de Orthanc
ORTHANC_URL = os.getenv("ORTHANC_URL", "http://localhost:8042")

# Credenciales (déjalas en blanco si Orthanc no usa auth)
ORTHANC_USER = os.getenv("ORTHANC_USER")
ORTHANC_PASS = os.getenv("ORTHANC_PASS")
AUTH = (ORTHANC_USER, ORTHANC_PASS) if ORTHANC_USER and ORTHANC_PASS else None

# Endpoint DICOMweb
DICOMWEB = f"{ORTHANC_URL}/dicom-web"
