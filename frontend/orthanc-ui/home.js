const ORTHANC_BASE_URL = ""; // mismo origen

function getStudyDetailUrl(studyId) {
  return `study.html?study=${encodeURIComponent(studyId)}`;
}

function getOhifUrlFromInstanceUID(uid) {
  const OHIF_BASE_URL = "http://localhost:3000"; // ajusta a tu entorno
  return `${OHIF_BASE_URL}/?StudyInstanceUID=${encodeURIComponent(uid)}`;
}

async function loadStudies() {
  const tbody = document.getElementById("studies-body");
  try {
    const resp = await fetch(`${ORTHANC_BASE_URL}/studies`);
    if (!resp.ok) throw new Error("No se pudo obtener la lista de estudios");
    const studyIds = await resp.json();

    if (!studyIds.length) {
      tbody.innerHTML =
        "<tr><td colspan='4'>No hay estudios cargados en Orthanc.</td></tr>";
      return;
    }

    // Limitar para la demo (por ejemplo 20 más recientes, invertidos)
    const ids = studyIds.slice().reverse().slice(0, 20);

    tbody.innerHTML = "";
    for (const id of ids) {
      const sResp = await fetch(`${ORTHANC_BASE_URL}/studies/${id}`);
      if (!sResp.ok) continue;
      const study = await sResp.json();

      const tags = study.MainDicomTags || {};
      const ptags = study.PatientMainDicomTags || {};
      const patientName = ptags.PatientName || "—";
      const desc = tags.StudyDescription || "Estudio sin descripción";
      const dateRaw = tags.StudyDate || "";
      const date =
        dateRaw.length === 8
          ? `${dateRaw.slice(6, 8)}/${dateRaw.slice(4, 6)}/${dateRaw.slice(
              0,
              4
            )}`
          : "—";
      const uid = tags.StudyInstanceUID || null;

      const tr = document.createElement("tr");
      const actions = [];

      // Botón: ver detalle PACS-AI (estudio)
      actions.push(
        `<button class="table-btn" onclick="window.location.href='${getStudyDetailUrl(
          id
        )}'">Detalle</button>`
      );

      // Botón: Ver en OHIF
      if (uid) {
        const ohifUrl = getOhifUrlFromInstanceUID(uid);
        actions.push(
          `<button class="table-btn secondary" onclick="window.open('${ohifUrl}','_blank')">Ver en OHIF</button>`
        );
      }

      tr.innerHTML = `
        <td>${patientName}</td>
        <td>${desc}</td>
        <td>${date}</td>
        <td>${actions.join(" ")}</td>
      `;
      tbody.appendChild(tr);
    }
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="4">Error al cargar estudios: ${err.message}</td></tr>`;
  }
}

function setupActions() {
  const btnUpload = document.getElementById("btn-upload");
  const btnView = document.getElementById("btn-view");
  const btnSearch = document.getElementById("btn-search");
  const searchInput = document.getElementById("search-input");
  const tableSection = document.getElementById("studies-section");

  // Subir DICOM -> ir a la pantalla de upload de Orthanc
  btnUpload.addEventListener("click", () => {
    // Ruta típica del explorer:
    window.location.href = "/app/explorer.html#upload";
  });

  // Ver estudios -> hacer scroll a la tabla
  btnView.addEventListener("click", () => {
    tableSection.scrollIntoView({ behavior: "smooth" });
  });

  // Buscar -> enfocar input
  btnSearch.addEventListener("click", () => {
    tableSection.scrollIntoView({ behavior: "smooth" });
    searchInput.focus();
  });

  // Filtro simple en cliente
  searchInput.addEventListener("input", () => {
    const text = searchInput.value.toLowerCase();
    const rows = document.querySelectorAll("#studies-body tr");
    rows.forEach((row) => {
      const cells = Array.from(row.querySelectorAll("td"));
      const hayTexto = cells.some((td) =>
        td.textContent.toLowerCase().includes(text)
      );
      row.style.display = hayTexto ? "" : "none";
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupActions();
  loadStudies();
});
