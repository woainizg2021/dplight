# Dplight ERP Backend

FastAPI backend service for Dplight ERP system.

## Prerequisites

- Python 3.9+
- MySQL (Shared Data & Exchange Rates)
- MSSQL (ERP Data)
- Redis (Caching)

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables (optional, defaults in `app/config.py`):
   - `REDIS_HOST`, `REDIS_PORT`
   - Database credentials are loaded from project root `config.py`

3. Initialize Database (Exchange Rates):
   ```bash
   python ../scripts/init_exchange_rates.py
   ```
   *Note: Ensure you have connectivity to the MySQL server.*

## Running the Server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

- `app/`: Application code
  - `routers/`: API endpoints
  - `services/`: Business logic and external connections
  - `models/`: Pydantic schemas
  - `config.py`: Configuration loader
- `main.py`: Entry point
