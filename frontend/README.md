📁 PACS-AI UI – Interfaz Personalizada para Orthanc

Interfaz web personalizada desarrollada para el proyecto PACS-AI Assist, diseñada para integrarse directamente con Orthanc Server mediante el módulo ServeFolders.
Permite visualizar estudios, acceder al visor, activar la IA y presentar una apariencia moderna adaptada al proyecto.

🧩 Características principales

UI completamente personalizada en HTML, CSS y JavaScript.

Integración directa con Orthanc a través de ServeFolders.

Compatible con la estructura REST de Orthanc.

Diseño liviano, responsivo y simple de mantener.

Se accede desde:

http://localhost:8042/pacsai/index.html

📦 Estructura del proyecto
orthanc-ui/
│── index.html
│── study.html
│── home.js
│── study.js
│── home.css
│── styles.css
└── README.md

Archivos principales
Archivo	Descripción
index.html	Página principal de la interfaz.
study.html	Vista individual de estudios.
home.js	Lógica del inicio, carga de estudios, interacción básica.
study.js	Lógica para visualizar datos específicos de un estudio.
home.css	Estilos generales del inicio.
styles.css	Estilos compartidos entre vistas.
🔧 Instalación en Orthanc (ServeFolders)

Para que Orthanc sirva esta interfaz como un sitio web interno, debes habilitar ServeFolders en el archivo:

C:\ProgramData\Orthanc\Configuration\orthanc.json


Agregar la siguiente configuración:

"ServeFolders": {
  "Enable": true,
  "Folders": {
    "/pacsai": "C:/Users/taiss/Desktop/Carpetas/CAPSTONE/PACS-AI-Assist/frontend/orthanc-ui"
  }
}


Luego reinicia Orthanc desde services.msc.

🧪 Cómo acceder a la interfaz

Una vez reiniciado Orthanc, ingresar desde cualquier navegador a:

http://localhost:8042/pacsai/index.html


Si ves tu UI en vez de la interfaz nativa de Orthanc, la integración está funcionando correctamente.

🚀 Uso general

Navega entre estudios usando home.js.

Haz clic en un estudio para abrir study.html.

La interfaz puede integrarse directamente con:

Backend de IA (Uvicorn/FastAPI)

Visor OHIF

Módulos del proyecto PACS-AI

🛠 Personalización

Puedes modificar colores, tamaños e interfaz ajustando:

home.css para el inicio.

styles.css para estilos globales.

index.html o study.html para estructura y textos.

📌 Notas importantes

Orthanc no recarga archivos automáticamente, siempre requiere reiniciar para ver cambios.

Las rutas deben ser absolutas y contener dobles backslashes en JSON.

Si Orthanc no detecta la carpeta, revisa permisos y rutas.

Este módulo es parte del proyecto académico PACS-AI Assist