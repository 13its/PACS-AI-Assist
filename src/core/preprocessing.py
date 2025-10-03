import time, json
import numpy as np
import SimpleITK as sitk
from pathlib import Path
import cv2

def resample_iso(img, spacing=(1.0,1.0,1.0)):
    original_spacing = img.GetSpacing()
    original_size = img.GetSize()
    new_size = [int(round(osz*ospc/nspc)) for osz,ospc,nspc in zip(original_size, original_spacing, spacing)]
    return sitk.Resample(
        img, new_size, sitk.Transform(), sitk.sitkLinear,
        img.GetOrigin(), spacing, img.GetDirection(), 0, img.GetPixelID()
    )

def window_lung(arr, wl=-600, ww=1500):
    low, high = wl - ww/2, wl + ww/2
    arr = np.clip(arr, low, high)
    return ((arr - low) / (high - low)).astype(np.float32)

def save_npz_and_thumbs(vol, out_dir: Path, step=10):
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir/"volume_resampled.npz", vol=vol)
    # thumbnails
    for i in range(0, vol.shape[0], step):
        sl = (vol[i] * 255).astype(np.uint8)
        cv2.imwrite(str(out_dir/f"thumb_{i:03d}.png"), sl)

def run_preprocess(img: sitk.Image, meta: dict, out_dir: Path):
    t0 = time.time()
    img_r = resample_iso(img, (1,1,1))
    t1 = time.time()
    arr = sitk.GetArrayFromImage(img_r).astype(np.float32)  # z,y,x
    arr = window_lung(arr, -600, 1500)
    save_npz_and_thumbs(arr, out_dir)
    t2 = time.time()

    timings = {"resample_s": round(t1-t0,3), "normalize_s": round(t2-t1,3), "total_s": round(t2-t0,3)}
    with open(out_dir/"meta.json", "w") as f: json.dump({"meta": meta, "timings": timings}, f, indent=2)
    return {"timings": timings, "out_dir": str(out_dir)}
