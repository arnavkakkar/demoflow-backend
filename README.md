# DemoFlow Backend

The backend service for **DemoFlow**, providing lead capture, A/B test telemetry tracking, and conversion funnel analytics. Built as a lightweight, single-file Flask application with SQLite storage.

> **Disclaimer:** This is a demo project. Do not enter real personal or sensitive data.

---

## Tech Stack

- **Language:** Python (3.x)
- **Web Framework:** [Flask](https://flask.palletsprojects.com/)
- **CORS Handling:** [flask-cors](https://flask-cors.readthedocs.io/)
- **Database:** Built-in [`sqlite3`](https://docs.python.org/3/library/sqlite3.html) (zero-configuration embedded database)

---

## Getting Started

### Prerequisites

- Python 3.8+ installed on your system.

### Installation & Run

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

The server will start at **`http://localhost:5001`**.

> **Note on Port 5001:** Port 5000 is reserved by macOS for AirPlay Receiver (`ControlCenter`). DemoFlow defaults to port `5001` (configurable via the `PORT` environment variable) to avoid port conflicts.

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check endpoint to verify backend operational status. |
| `POST` | `/lead` | Captures demo request form submissions and saves them into the SQLite `leads` table. |
| `POST` | `/event` | Records telemetry events (`view` or `click`) for A/B testing variants (`A` or `B`). |
| `GET` | `/results` | Renders an internal HTML dashboard comparing performance metrics across variants. |
| `GET` | `/api/results` | Returns aggregated A/B testing metrics (views, clicks, leads, rates) in JSON format. |

### Request Bodies for POST Endpoints

#### `POST /lead`
Receives demo request form submissions. `name` and `email` (must contain `@`) are required.

**Example Request Body:**
```json
{
  "name": "Alex Mercer",
  "email": "alex@example.com",
  "company": "Acme Innovations",
  "variant": "A"
}
```

**Success Response (HTTP 201):**
```json
{
  "success": true
}
```

#### `POST /event`
Logs visitor telemetry for variant analysis. `event_type` must be `"view"` or `"click"`, and `variant` must be `"A"` or `"B"`.

**Example Request Body:**
```json
{
  "event_type": "view",
  "variant": "A"
}
```

**Success Response (HTTP 201):**
```json
{
  "success": true
}
```

---

## Metrics Calculation & Funnel Logic

Metrics displayed on `/results` and returned by `/api/results` are computed as follows:

- **Click Rate:**
  $$\text{Click Rate} = \left(\frac{\text{clicks}}{\text{views}}\right) \times 100$$
  Measures top-of-funnel CTA engagement for each headline/CTA variant.
- **Conversion Rate:**
  $$\text{Conversion Rate} = \left(\frac{\text{leads}}{\text{views}}\right) \times 100$$
  Measures full-funnel effectiveness from initial landing view to completed demo request.
- **Session De-duplication:** Views are counted once per browser session by the frontend (using `sessionStorage`) to prevent repeat impression skew and avoid double-counting caused by React StrictMode during local development.
- **Zero-Division Protection:** If `views == 0`, click and conversion rates safely default to `0.0%`.

---

## CORS & Frontend Integration

- **Allowed CORS Origins:** Cross-Origin Resource Sharing is enabled via `CORS(app)` without origin restrictions (allowing `*`), enabling requests from the Next.js frontend running locally on `http://localhost:3000` (or `http://localhost:3005`).
- **Frontend Repository:** The Next.js frontend lives in a separate repository (`demoflow-frontend`).

---

## Architecture & Database Notes

- **Database (`leads.db`):** The SQLite database file is created automatically on the first run by `init_db()` if it does not already exist. It contains two tables (`leads` and `events`). The database file is excluded from version control via `.gitignore`.
- **Inline Results Template:** The `/results` reporting dashboard renders its HTML inline using Flask's `render_template_string`. Because this is a lightweight internal reporting view, keeping the template inline avoids extra template directories and keeps the backend completely self-contained in `app.py`.
