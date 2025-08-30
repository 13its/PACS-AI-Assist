# PACS-AI Assist
**An AI-powered assistant for predictive medical imaging diagnostics**

## 🚀 Overview
PACS-AI Assist is a Capstone project that simulates the integration of an AI model with hospital imaging systems (PACS) using the DICOM standard.  
The use case is the **early detection of lung cancer** in CT scans.

## 🔹 Features
- Integration with a simulated PACS (Orthanc).
- Processing and analysis of DICOM studies.
- Predictive model to detect lung nodules.
- Results exported as **DICOM SEG** (segmentations) and **DICOM SR** (structured reports).
- Visualization via **OHIF Viewer**.

## 📊 Validation
Validation will be done with the **LIDC-IDRI dataset**, which includes radiologist annotations.  
Metrics used:
- Sensitivity & Specificity  
- AUC-ROC  
- Dice Score (for segmentation)  
- Brier Score (for probability calibration)

## ⚖️ Ethical Note
All data used is **public and anonymized**. This project is for academic purposes only and does not replace medical diagnosis.

## 📂 Repository Structure
- `docs/` – Documentation  
- `src/` – Source code  
- `notebooks/` – Prototypes and experiments  
- `data/` – Dataset instructions  

## 🔧 Requirements
- Python 3.10+  
- `pydicom`, `pynetdicom`, `dicomweb-client`, `highdicom`  
- `numpy`, `pandas`, `scikit-learn`  
- `torch` or `tensorflow`  

## 👤 Author
Diego Alexis – Capstone Project, Ingeniería en Informática
