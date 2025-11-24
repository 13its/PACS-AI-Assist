const ORTHANC_BASE_URL = ""; // mismo origen
const OHIF_BASE_URL = "http://localhost:3000"; // ajusta si es distinto

function getQueryParam(name) {
  const params = new URLSearchParams(window.location.search);
  return params.get(name);
}

function formatDate(yyyymmdd) {
  if (!yyyymmdd || yyyymmdd.length !== 8) return "–";
  const y = yyyymmdd.slice(0, 4);
  const m = yyyymmdd.slice(4, 6);
  const d = yyyymmdd.slice(6, 8);
  return `${d}/${m}/${y}`;
}

function safeTag(obj, key, fallback = "–") {
  return obj && obj[key] ? obj[key] : fallback;
}

async function loadStudy() {
  const studyId = getQueryParam("study");
  const seriesBody = document.getElementById("series-body");
  const btnOhif = document.getElementById("btn-ohif");
  const helper = document.getElementById("ohif-helper");

  if (!studyId) {
    seriesBody.innerHTML =
      "<tr><td colspan='3'>Falta el parámetro <code>?study=ID</code> en la URL.</td></tr>";
    helper.textContent =
      "Esta vista está pensada para ser abierta desde el listado de estudios de PACS-AI Assist.";
    return;
  }

  try {
    const studyResp = await fetch(`${ORTHANC_BASE_URL}/studies/${studyId}`);
    if (!studyResp.ok) throw new Error("No se encontró el estudio.");
    const study = await studyResp.json();

    const tags = study.MainDicomTags || {};
    const patientTags = study.PatientMainDicomTags || {};

    document.getElementById("patient-id").textContent = safeTag(
      patientTags,
      "PatientID"
    );
    document.getElementById("patient-name").textContent = safeTag(
      patientTags,
      "PatientName"
    );
    document.getElementById("patient-birth").textContent = formatDate(
      safeTag(patientTags, "PatientBirthDate", "")
    );
    document.getElementById("patient-sex").textContent = safeTag(
      patientTags,
      "PatientSex"
    );

    document.getElementById("study-date").textContent = formatDate(
      safeTag(tags, "StudyDate", "")
    );
    document.getElementById("study-desc").textContent = safeTag(
      tags,
      "StudyDescription"
    );
    document.getElementById("study-body-part").textContent = safeTag(
      tags,
      "BodyPartExamined"
    );

    // Series
    const seriesIds = study.Series || [];
    if (!seriesIds.length) {
      seriesBody.innerHTML =
        "<tr><td colspan='3'>Este estudio no tiene series asociadas.</td></tr>";
    } else {
      seriesBody.innerHTML = "";
      for (const sid of seriesIds) {
        const sResp = await fetch(`${ORTHANC_BASE_URL}/series/${sid}`);
        if (!sResp.ok) continue;
        const s = await sResp.json();
        const stags = s.MainDicomTags || {};
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${safeTag(stags, "SeriesDescription")}</td>
          <td>${s.Instances ? s.Instances.length : "–"} imágenes</td>
          <td>${safeTag(stags, "Modality")}</td>
        `;
        seriesBody.appendChild(row);
      }
    }

    // OHIF
    const studyInstanceUID = safeTag(tags, "StudyInstanceUID", null);
    if (studyInstanceUID) {
      const ohifUrl = `${OHIF_BASE_URL}/?StudyInstanceUID=${encodeURIComponent(
        studyInstanceUID
      )}`;
      btnOhif.disabled = false;
      btnOhif.addEventListener("click", () => {
        window.open(ohifUrl, "_blank");
      });
    } else {
      helper.textContent =
        "No se encontró StudyInstanceUID; es posible que este estudio no pueda abrirse en OHIF.";
    }
  } catch (err) {
    console.error(err);
    seriesBody.innerHTML = `<tr><td colspan="3">Error al cargar el estudio: ${err.message}</td></tr>`;
    helper.textContent =
      "Verifica que el ID del estudio sea válido y que Orthanc esté en línea.";
  }
}

document.addEventListener("DOMContentLoaded", loadStudy);
