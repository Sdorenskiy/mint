# MINT in a container — for trying it out together with Ollama (docker-compose.yml).
# For a regular installation on a computer see docs/INSTALL.md.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt .
# Docling's slim build (only the .docx reader): no PyTorch, no OpenCV, no models; .pdf is read by pdfplumber
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8501
# Inside the container the page listens on all container interfaces; on the host the port is published
# on localhost only (see ports in docker-compose.yml).
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0"]
