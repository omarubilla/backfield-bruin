"""Modal deployment of the Bruin benchmark API (HTTPS).

    scripts/build_serving_db.py          # refresh data/serving.duckdb from the Bruin run
    modal deploy deploy/modal_app.py

Secret: Modal secret 'backfield-bruin-api' with BRUIN_API_TOKEN (guards /v1/private/*).
The image contains only the serving DB (gold tables), the run-status JSON, the schema and code -
no .env, no PFF key, no raw bronze PFF rows.
"""
import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("google-auth==2.36.0", "requests==2.32.3", "fastapi[standard]==0.115.6", "duckdb==2.0.1")
    .env({"BRUIN_DUCKDB": "/app/data/serving.duckdb", "BRUIN_RUN_STATUS": "/app/logs/bruin_run_latest.json",
          "BRUIN_SCHEMA": "/app/docs/athlete_benchmark.schema.json", "BRUIN_LINEAGE": "/app/docs/evidence/lineage.json", "PYTHONPATH": "/app", "LIVE_LANDING_DIR": "/landing/assessments", "FIREBASE_PROJECT_ID": "backfield-17607"})
    .add_local_dir("bruin_export", "/app/bruin_export", ignore=["__pycache__"])
    .add_local_file("api/serving_api.py", "/app/api/serving_api.py")
    .add_local_file("api/live_routes.py", "/app/api/live_routes.py")
    .add_local_file("api/__init__.py", "/app/api/__init__.py")
    .add_local_file("data/serving.duckdb", "/app/data/serving.duckdb")
    .add_local_file("logs/bruin_run_latest.json", "/app/logs/bruin_run_latest.json")
    .add_local_file("docs/athlete_benchmark.schema.json", "/app/docs/athlete_benchmark.schema.json")
    .add_local_file("docs/evidence/lineage.json", "/app/docs/evidence/lineage.json")
)

app = modal.App("backfield-bruin-api", image=image)
landing = modal.Volume.from_name("backfield-bruin-assessments", create_if_missing=True)


@app.function(secrets=[modal.Secret.from_name("backfield-bruin-api", required_keys=["BRUIN_API_TOKEN"])],
              volumes={"/landing": landing}, scaledown_window=900, max_containers=3)
@modal.concurrent(max_inputs=50)
@modal.asgi_app(label="backfield-bruin-api")
def web():
    from api import live_routes
    from api.serving_api import app as api
    live_routes.set_volume(landing)
    return api
