# PACS-AI Assist

Proyecto integrador para procesamiento de imágenes médicas (DICOM) con IA.  
El objetivo es crear un asistente que procese estudios DICOM, preprocese los volúmenes y deje la data lista para etapas posteriores de análisis e inferencia.

---

## 🚀 Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/13its/PACS-AI-Assist.git
cd PACS-AI-Assist
```

### 2. Crear y activar entorno virtual
En **Windows (PowerShell)**:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En **Linux/Mac**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

---

## 📂 Estructura del proyecto

```
PACS-IA Assist/
├── Fase1/                     
├── Fase2/
│   └── Evidencias_Proyecto/   # Evidencias Sprint 2 (logs, meta, thumbs, freeze)
├── Fase3/
├── src/
│   ├── api/                   # Endpoints FastAPI
│   ├── core/                  # Funciones núcleo (IO, preprocessing, utils)
│   └── scripts/               # Scripts ejecutables
├── requirements.txt           
├── requirements-freeze.txt    
└── README.md
```

---

## ▶️ Uso del pipeline

Ejecutar el preprocesamiento sobre una carpeta con estudios **DICOM**:

```powershell
python -m src.scripts.run_preproc --input_dir "C:\ruta\a\carpeta\con\dcm"
```

### Parámetros:
- `--input_dir` → ruta a la carpeta que contiene los archivos `.dcm`.

---

## 📊 Resultados

Al ejecutar, se generan:

- **Artefactos** → en `artifacts/YYYYMMDD/<UID>/`  
  - `meta.json` → metadatos de la serie procesada.  
  - `volume_resampled.npz` → volumen en numpy comprimido.  
  - `thumb_*.png` → cortes axiales en PNG (para revisión rápida).  

- **Logs** → en `logs/pipeline.jsonl`  
  - Registro JSONL con eventos.  
  - Incluye `event: preprocess_ok`, input, out_dir y timings.

Ejemplo de log:
```json
{
  "level": "INFO",
  "event": "preprocess_ok",
  "input": "C:\...\3000566.000000-NA-03192",
  "out_dir": "artifacts\20251002\1759451923",
  "timings": {"resample_s": 0.285, "normalize_s": 6.504, "total_s": 6.789},
  "ts": 1759451930.367,
  "host": "DESKTOP-A9OA2MS"
}
```

---

## ✅ Sprint 2 – Criterios cumplidos

- [x] Pipeline backend en Python que procesa series DICOM.  
- [x] Librerías documentadas (`requirements.txt`, `requirements-freeze.txt`).  
- [x] Artefactos intermedios y logs generados.  
- [x] Ejecución en batch con estado (`OK=1 FAIL=0`).  

---

## 🔜 Próximos pasos (Sprint 3)

- Implementar endpoint `/infer/dicom` para inferencia dummy (detección sintética de nódulos).  
- Generar overlays PNG sobre los cortes procesados.  
- Integración con Orthanc / PACS para flujo de extremo a extremo.

---

## 👥 Equipo

- **Diego Castañeda** – Desarrollo backend y pipeline IA.  
- (agregar integrantes según roles: PO, Scrum Master, etc.)
