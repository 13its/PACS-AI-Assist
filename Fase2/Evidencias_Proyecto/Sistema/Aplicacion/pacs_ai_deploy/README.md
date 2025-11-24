# PACS-AI Assist — Despliegue rápido
1. Descomprime: `unzip pacs_ai_deploy.zip && cd pacs_ai_deploy`
2. Ejecuta: `docker compose up --build`
3. Prueba el backend: `curl http://localhost:8000/status`
Tu modelo (`best_cnn3d.keras`) se carga automáticamente.