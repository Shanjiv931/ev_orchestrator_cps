FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# --reload matches the frontend's Vite dev server already auto-applying
# source changes - without it, backend/ being bind-mounted for live editing
# is misleading: edits land on disk but the running server keeps serving
# whatever was in memory at container start until manually restarted,
# which is exactly what caused a real bug to look unfixed during this
# project's own development.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
