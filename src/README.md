# PACS-AI Assist
**An AI-powered assistant for predictive medical imaging diagnostics**  
**Un asistente predictivo con IA para diagnósticos médicos integrados al estándar DICOM**

---

## 🌍 Overview / Descripción
**EN:**  
PACS-AI Assist is a Capstone project that simulates the integration of an AI model with hospital imaging systems (PACS) using the DICOM standard.  
The use case is the early detection of lung cancer in CT scans.

**ES:**  
PACS-AI Assist es un proyecto de Capstone que simula la integración de un modelo de IA con los sistemas hospitalarios de imágenes médicas (PACS) usando el estándar DICOM.  
El caso de uso es la detección temprana de cáncer de pulmón en estudios de tomografía computarizada (CT).

---

## ⚙️ Features / Funcionalidades
- **EN:** Integration with a simulated PACS (Orthanc).  
- **ES:** Integración con un PACS simulado (Orthanc).  

- **EN:** Processing and analysis of DICOM studies.  
- **ES:** Procesamiento y análisis de estudios DICOM.  

- **EN:** Predictive model to detect lung nodules.  
- **ES:** Modelo predictivo para detectar nódulos pulmonares.  

- **EN:** Results exported as DICOM SEG (segmentations) and DICOM SR (structured reports).  
- **ES:** Resultados exportados como DICOM SEG (segmentaciones) y DICOM SR (reportes estructurados).  

- **EN:** Visualization via OHIF Viewer.  
- **ES:** Visualización a través de OHIF Viewer.  

---

## 📊 Validation / Validación
**EN:** Validation will be done with the LIDC-IDRI dataset, which includes radiologist annotations. Metrics used:  
- Sensitivity & Specificity  
- AUC-ROC  
- Dice Score (for segmentation)  
- Brier Score (for probability calibration)  

**ES:** La validación se realizará con el dataset LIDC-IDRI, que incluye anotaciones de radiólogos. Se usarán métricas como:  
- Sensibilidad y Especificidad  
- AUC-ROC  
- Dice Score (para segmentación)  
- Brier Score (para calibración de probabilidades)  

---

## ⚖️ Ethical Note / Nota Ética
**EN:** All data used is public and anonymized. This project is for academic purposes only and does not replace medical diagnosis.  
**ES:** Todos los datos usados son públicos y anonimizados. Este proyecto es únicamente con fines académicos y no reemplaza el diagnóstico médico.  

---

## 📂 Repository Structure / Estructura del Repositorio
- `docs/` – Documentation / Documentación  
- `src/` – Source code / Código fuente  
- `notebooks/` – Prototypes and experiments / Prototipos y experimentos  
- `data/` – Dataset instructions / Instrucciones del dataset  

---

## 🔧 Requirements / Requisitos
- Python 3.10+  
- Libraries / Librerías: `pydicom`, `pynetdicom`, `dicomweb-client`, `highdicom`, `numpy`, `pandas`, `scikit-learn`, `torch` or `tensorflow`  

---

## 👤 Author / Autor
Diego Alexis – Capstone Project, Ingeniería en Informática
