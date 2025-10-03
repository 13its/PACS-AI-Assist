from pathlib import Path
import SimpleITK as sitk
import json, time

def load_series_from_folder(path: Path):
    reader = sitk.ImageSeriesReader()
    series = reader.GetGDCMSeriesFileNames(str(path))
    if not series:
        raise RuntimeError(f"No DICOM series in {path}")
    reader.SetFileNames(series)
    img = reader.Execute()
    meta = {
        "size": img.GetSize(),
        "spacing": img.GetSpacing(),
        "origin": img.GetOrigin(),
        "direction": img.GetDirection(),
        "series_count": len(series)
    }
    return img, meta
