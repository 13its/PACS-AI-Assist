# Levantar el servidor FastAPI (overlay)

Estos pasos se ejecutan en PowerShell en Windows.

1) Abrir PowerShell y situarse en la carpeta del overlay:

```
cd 'c:\Users\Jamsd\OneDrive\Documentos\GitHub\PACS-AI-Assist\src\overlay'
```

2) Crear y activar un entorno virtual:

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la ejecución del script, habilita la ejecución temporalmente (ejecutar como administrador si es necesario):

```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

3) Instalar dependencias:

```
pip install --upgrade pip
pip install -r requirements.txt
```

4) Ejecutar el servidor (desarrollo con recarga automática):

```
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

O ejecutar directamente el script:

```
python server.py
```

5) Verificar:

- Documentación OpenAPI: http://127.0.0.1:8000/docs
- WebSocket: ws://127.0.0.1:8000/ws
- Endpoint POST: http://127.0.0.1:8000/push