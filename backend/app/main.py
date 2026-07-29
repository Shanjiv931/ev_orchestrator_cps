from fastapi import FastAPI

app = FastAPI(title="EV Charging Orchestrator API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
