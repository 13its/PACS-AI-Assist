import os
import pydicom
import matplotlib.pyplot as plt

# ruta de ejemplo (ajusta después al dataset que descarguemos)
dcm_file = "ruta/a/tu/archivo.dcm"

# leer el archivo DICOM
ds = pydicom.dcmread(dcm_file)

print("Paciente:", ds.PatientID)
print("Modalidad:", ds.Modality)

# visualizar la imagen
plt.imshow(ds.pixel_array, cmap="gray")
plt.title("Imagen DICOM")
plt.axis("off")
plt.show()
