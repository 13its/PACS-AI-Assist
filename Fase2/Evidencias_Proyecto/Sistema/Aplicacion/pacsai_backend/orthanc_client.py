# orthanc_client.py
from typing import Tuple, List
import io, os, requests, numpy as np, pydicom

from settings import DICOMWEB, ORTHANC_URL, AUTH

# Tags DICOM (hex)
TAG_MODALITY = "00080060"                 # Modality
TAG_SERIES_INSTANCE_UID = "0020000E"     # SeriesInstanceUID
TAG_NUM_SERIES_RELATED_INST = "00201209" # NumberOfSeriesRelatedInstances
TAG_SOP_INSTANCE_UID = "00080018"        # SOPInstanceUID
TAG_IMAGE_POSITION_PATIENT = "00200032"  # ImagePositionPatient

def _val(tagobj):
    v = tagobj.get("Value")
    return v[0] if isinstance(v, list) and v else None

def _get_hex(d: dict, tag: str, default=None):
    try:
        if tag in d:
            return _val(d[tag])
    except Exception:
        pass
    return default

# ---------- DICOMweb (QIDO/WADO) ----------

def qido_series(study_uid: str) -> list:
    r = requests.get(
        f"{DICOMWEB}/series",
        params={"StudyInstanceUID": study_uid, "includefield": "all", "limit": 9999},
        auth=AUTH,
    )
    r.raise_for_status()
    return r.json()

def qido_instances(study_uid: str, series_uid: str) -> list:
    r = requests.get(
        f"{DICOMWEB}/instances",
        params={
            "StudyInstanceUID": study_uid,
            "SeriesInstanceUID": series_uid,
            "includefield": "all",
            "limit": 99999,
        },
        auth=AUTH,
    )
    r.raise_for_status()
    return r.json()

def wado_instance(study_uid: str, series_uid: str, sop_uid: str) -> pydicom.Dataset:
    # 1) WADO-RS
    try:
        url = f"{DICOMWEB}/studies/{study_uid}/series/{series_uid}/instances/{sop_uid}"
        r = requests.get(url, headers={"Accept": "application/dicom"}, auth=AUTH)
        r.raise_for_status()
        if "application/dicom" in r.headers.get("Content-Type", "").lower() or r.content:
            return pydicom.dcmread(io.BytesIO(r.content), force=True)
    except requests.HTTPError:
        pass  # caemos al fallback

    # 2) Fallback: REST nativa de Orthanc (lookup correcto)
    # reemplaza el bloque fallback por:
    lr = requests.post(f"{ORTHANC_URL}/tools/find",
                    json={"Level":"Instance","Query":{"SOPInstanceUID": sop_uid}},
                    auth=AUTH)
    lr.raise_for_status()
    hits = lr.json()
    inst_id = hits[0] if hits else None
    if not inst_id:
        raise RuntimeError(f"No se pudo resolver Orthanc ID para SOP {sop_uid}")


    fr = requests.get(f"{ORTHANC_URL}/instances/{inst_id}/file", auth=AUTH)
    fr.raise_for_status()
    return pydicom.dcmread(io.BytesIO(fr.content), force=True)

def pick_ct_series(study_series: list) -> str:
    candidates: List[tuple[int, str]] = []
    for s in study_series:
        if _get_hex(s, TAG_MODALITY, "") != "CT":
            continue
        n = _get_hex(s, TAG_NUM_SERIES_RELATED_INST, 0) or 0
        try:
            n = int(n)
        except Exception:
            n = 0
        suid = _get_hex(s, TAG_SERIES_INSTANCE_UID, None)
        if suid:
            candidates.append((n, suid))
    if not candidates:
        raise RuntimeError("No se encontraron series CT en el estudio (QIDO vacío).")
    candidates.sort(reverse=True)
    return candidates[0][1]

def load_volume_sorted(study_uid: str, series_uid: str) -> Tuple[np.ndarray, list]:
    inst = qido_instances(study_uid, series_uid)

    def key_ipp(i):
        ipp = _get_hex(i, TAG_IMAGE_POSITION_PATIENT, None)
        if isinstance(ipp, list) and len(ipp) == 3:
            try:
                return float(ipp[2])
            except Exception:
                return 0.0
        return 0.0

    inst_sorted = sorted(inst, key=key_ipp)
    if not inst_sorted:
        raise RuntimeError("La serie seleccionada no tiene instancias (QIDO Instances vacío).")

    ds_list, vol = [], []
    for it in inst_sorted:
        sop = _get_hex(it, TAG_SOP_INSTANCE_UID, None)
        if not sop:
            continue
        ds = wado_instance(study_uid, series_uid, sop)
        ds_list.append(ds)
        vol.append(ds.pixel_array.astype(np.int16))

    if not vol:
        raise RuntimeError("No se pudieron cargar instancias DICOM de la serie seleccionada.")
    volume = np.stack(vol, axis=0)
    return volume, ds_list

# ---------- REST Orthanc helpers ----------

def _post(path, json):
    r = requests.post(f"{ORTHANC_URL}{path}", json=json, auth=AUTH)
    r.raise_for_status()
    return r.json()

def _get(path):
    r = requests.get(f"{ORTHANC_URL}{path}", auth=AUTH)
    r.raise_for_status()
    return r.json()

def find_series_ids_ct(study_uid: str):
    return _post("/tools/find", {"Level": "Series", "Query": {"StudyInstanceUID": study_uid, "Modality": "CT"}})

def get_series_uid(series_id: str):
    info = _get(f"/series/{series_id}")
    return info["MainDicomTags"]["SeriesInstanceUID"]

def get_instances_of_series(series_id: str):
    info = _get(f"/series/{series_id}")
    return info.get("Instances", [])

def get_instance_tags(inst_id: str):
    return _get(f"/instances/{inst_id}/tags")

def lookup_instance_id(sop_uid: str):
    hits = _post("/tools/find", {
        "Level": "Instance",
        "Query": { "SOPInstanceUID": sop_uid }
    })
    if not hits:
        raise RuntimeError(f"Instance no encontrada para SOP {sop_uid}")
    return hits[0]


