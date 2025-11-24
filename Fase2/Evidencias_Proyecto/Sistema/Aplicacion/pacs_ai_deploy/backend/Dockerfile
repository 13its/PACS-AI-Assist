FROM python:3.10-slim
WORKDIR /app
COPY backend_inference.py requirements.txt ./
COPY best_cnn3d.keras model_meta.json ./
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8000
CMD ['uvicorn','backend_inference:app','--host','0.0.0.0','--port','8000']
