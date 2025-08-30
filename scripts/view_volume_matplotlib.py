from pathlib import Path
import pydicom, numpy as np, matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from collections import defaultdict

BASE = Path("data/LIDC-IDRI_subset")
manifest = sorted([p for p in BASE.iterdir() if p.is_dir() and p.name.startswith("manifest-")])[-1]
DATA_ROOT = manifest / "LIDC-IDRI"
patient = max([p for p in DATA_ROOT.iterdir() if p.is_dir()], key=lambda p: sum(1 for _ in p.rglob("*.dcm")))

series = defaultdict(list)
for fp in patient.rglob("*.dcm"):
    try:
        ds = pydicom.dcmread(fp, stop_before_pixels=True, force=True)
        uid = getattr(ds, "SeriesInstanceUID", None)
        if uid: series[uid].append(fp)
    except Exception:
        pass

def good(uid, files):
    for f in files[:2]:
        try:
            ds = pydicom.dcmread(f, force=True)
            _ = ds.pixel_array
            return True
        except Exception:
            pass
    return False

uid, files = next((u, fs) for u, fs in sorted(series.items(), key=lambda kv: -len(kv[1])) if good(u, fs))
files = sorted(files, key=lambda f: (
    (getattr(pydicom.dcmread(f, stop_before_pixels=True, force=True), "ImagePositionPatient", [None,None,None])[2] is None),
    getattr(pydicom.dcmread(f, stop_before_pixels=True, force=True), "ImagePositionPatient", [0,0,0])[2],
    getattr(pydicom.dcmread(f, stop_before_pixels=True, force=True), "InstanceNumber", 0),
    str(f)
))
ex = pydicom.dcmread(files[0], force=True)
slope = float(getattr(ex,"RescaleSlope",1.0) or 1.0)
intercept = float(getattr(ex,"RescaleIntercept",0.0) or 0.0)
VOL = np.stack([pydicom.dcmread(f, force=True).pixel_array.astype(np.float32)*slope+intercept for f in files], axis=0)

wl, ww = -600.0, 1500.0
vmin, vmax = wl-ww/2, wl+ww/2
z0 = VOL.shape[0]//2
fig, ax = plt.subplots(figsize=(6,6))
plt.subplots_adjust(bottom=0.15)
im = ax.imshow(VOL[z0], cmap="gray", vmin=vmin, vmax=vmax); ax.axis("off")
ax_z = plt.axes([0.2, 0.05, 0.6, 0.03]); s_z = Slider(ax_z, "z", 0, VOL.shape[0]-1, valinit=z0, valstep=1)
def update(_): im.set_data(VOL[int(s_z.val)]); fig.canvas.draw_idle()
s_z.on_changed(update)
plt.show()
