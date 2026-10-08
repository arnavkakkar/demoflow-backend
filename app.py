import os
import sqlite3
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

# Create Flask application instance
app = Flask(__name__)

# CORS (Cross-Origin Resource Sharing):
# Allows our Next.js frontend running on http://localhost:3000 (or 3005)
# to make fetch requests to this Flask backend running on http://localhost:5001.
CORS(app)

# Database file location
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")

def init_db():
    """
    Initializes SQLite database tables on application startup.
    - leads: stores demo request form submissions
    - events: stores telemetry events ("view" and "click") per A/B variant
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table 1: Leads submitted via demo request form
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            company TEXT,
            variant TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 2: A/B testing events (Step 4)
    # event_type: "view" or "click"
    # variant: "A" or "B"
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            variant TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

# Run database setup immediately on startup
init_db()

def calculate_stats():
    """
    HOW RESULTS NUMBERS ARE CALCULATED:
    1. views: Count of 'view' events in the events table for each variant.
    2. clicks: Count of 'click' events in the events table for each variant.
    3. leads: Count of rows in the leads table for each variant.
    4. Click Rate: (clicks / views) * 100. Measures CTA engagement.
    5. Conversion Rate: (leads / views) * 100. Measures full funnel conversion.
    * Protection against division by zero: If views == 0, rates default to 0.0%.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {}
    for v in ["A", "B"]:
        # Count views for this variant
        cursor.execute("SELECT COUNT(*) FROM events WHERE event_type = 'view' AND variant = ?", (v,))
        views = cursor.fetchone()[0]

        # Count clicks for this variant
        cursor.execute("SELECT COUNT(*) FROM events WHERE event_type = 'click' AND variant = ?", (v,))
        clicks = cursor.fetchone()[0]

        # Count leads for this variant
        cursor.execute("SELECT COUNT(*) FROM leads WHERE variant = ?", (v,))
        leads = cursor.fetchone()[0]

        # Avoid division by zero
        click_rate = round((clicks / views * 100), 1) if views > 0 else 0.0
        conversion_rate = round((leads / views * 100), 1) if views > 0 else 0.0

        stats[v] = {
            "variant": v,
            "views": views,
            "clicks": clicks,
            "leads": leads,
            "click_rate": f"{click_rate:.1f}%",
            "conversion_rate": f"{conversion_rate:.1f}%",
            "click_rate_numeric": click_rate,
            "conversion_rate_numeric": conversion_rate,
        }

    conn.close()
    return stats

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint to verify backend status."""
    return jsonify({"status": "ok"}), 200

@app.route("/lead", methods=["POST"])
def submit_lead():
    """
    POST /lead: Receives demo request form submissions.
    Validates name and email, and inserts a row into SQLite leads table.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body. JSON payload is required."}), 400

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    company = str(data.get("company", "")).strip()
    variant = str(data.get("variant", "")).strip().upper()

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if not email or "@" not in email:
        return jsonify({"error": "A valid email containing '@' is required."}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO leads (name, email, company, variant) VALUES (?, ?, ?, ?)",
            (name, email, company, variant)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    return jsonify({"success": True}), 201

@app.route("/event", methods=["POST"])
def track_event():
    """
    POST /event: Records an A/B test telemetry event.
    - event_type: must be "view" or "click"
    - variant: must be "A" or "B"
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body. JSON payload is required."}), 400

    event_type = str(data.get("event_type", "")).strip().lower()
    variant = str(data.get("variant", "")).strip().upper()

    # Validation
    if event_type not in ["view", "click"]:
        return jsonify({"error": "event_type must be 'view' or 'click'"}), 400
    if variant not in ["A", "B"]:
        return jsonify({"error": "variant must be 'A' or 'B'"}), 400

    # SQL Insert using parameterized query
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (event_type, variant) VALUES (?, ?)",
            (event_type, variant)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    return jsonify({"success": True}), 201

@app.route("/api/results", methods=["GET"])
def api_results():
    """GET /api/results: Returns aggregated A/B test metrics as JSON."""
    return jsonify(calculate_stats()), 200

@app.route("/results", methods=["GET"])
def results_page():
    """
    GET /results: Renders an HTML report comparing Variant A and Variant B.
    Uses render_template_string for zero extra template dependencies.
    """
    stats = calculate_stats()

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DemoFlow | A/B Test Results</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #030712;
                color: #f3f4f6;
                padding: 40px 20px;
                line-height: 1.6;
            }
            .container {
                max-width: 960px;
                margin: 0 auto;
            }
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 16px;
                padding-bottom: 24px;
                margin-bottom: 32px;
                border-bottom: 1px solid #1f2937;
            }
            h1 {
                font-size: 26px;
                font-weight: 800;
                color: #ffffff;
            }
            h1 span {
                color: #818cf8;
            }
            .subtitle {
                font-size: 14px;
                color: #9ca3af;
                margin-top: 4px;
            }
            .refresh-btn {
                background-color: #4f46e5;
                color: white;
                padding: 9px 18px;
                border-radius: 8px;
                text-decoration: none;
                font-size: 13px;
                font-weight: 600;
                transition: background 0.2s;
            }
            .refresh-btn:hover {
                background-color: #4338ca;
            }
            .card {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
                margin-bottom: 32px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                text-align: left;
                font-size: 14px;
            }
            th {
                background-color: #1e293b;
                color: #94a3b8;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 11px;
                letter-spacing: 0.05em;
                padding: 14px 18px;
                border-bottom: 1px solid #334155;
            }
            td {
                padding: 16px 18px;
                border-bottom: 1px solid #1f2937;
            }
            tr:last-child td {
                border-bottom: none;
            }
            tr:hover td {
                background-color: rgba(99, 102, 241, 0.04);
            }
            .badge {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 20px;
                font-weight: 700;
                font-size: 12px;
            }
            .badge-a { background-color: #1e1b4b; color: #a5b4fc; border: 1px solid #3730a3; }
            .badge-b { background-color: #064e3b; color: #6ee7b7; border: 1px solid #047857; }
            .metric {
                font-weight: 600;
                color: #ffffff;
            }
            .highlight-rate {
                color: #38bdf8;
                font-weight: 700;
            }
            .highlight-conv {
                color: #34d399;
                font-weight: 700;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 16px;
            }
            .info-box {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 10px;
                padding: 16px;
            }
            .info-box h3 {
                font-size: 13px;
                color: #e2e8f0;
                margin-bottom: 6px;
                font-weight: 600;
            }
            .info-box p {
                font-size: 12px;
                color: #9ca3af;
                line-height: 1.5;
            }
            .footer-links {
                margin-top: 36px;
                text-align: center;
                font-size: 12px;
                color: #6b7280;
            }
            .footer-links a {
                color: #818cf8;
                text-decoration: none;
            }
            .footer-links a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h1>Demo<span>Flow</span> A/B Test Results</h1>
                    <div class="subtitle">Live variant performance metrics and conversion funnel</div>
                </div>
                <div>
                    <a href="/results" class="refresh-btn">↻ Refresh Data</a>
                </div>
            </div>

            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Variant</th>
                            <th>Headline Theme</th>
                            <th>CTA Button</th>
                            <th>Views</th>
                            <th>Clicks</th>
                            <th>Leads</th>
                            <th>Click Rate</th>
                            <th>Conversion Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><span class="badge badge-a">Variant A</span></td>
                            <td>Feature-focused</td>
                            <td>Request a Demo</td>
                            <td class="metric">{{ stats.A.views }}</td>
                            <td class="metric">{{ stats.A.clicks }}</td>
                            <td class="metric">{{ stats.A.leads }}</td>
                            <td class="highlight-rate">{{ stats.A.click_rate }}</td>
                            <td class="highlight-conv">{{ stats.A.conversion_rate }}</td>
                        </tr>
                        <tr>
                            <td><span class="badge badge-b">Variant B</span></td>
                            <td>Benefit-focused</td>
                            <td>See It in Action</td>
                            <td class="metric">{{ stats.B.views }}</td>
                            <td class="metric">{{ stats.B.clicks }}</td>
                            <td class="metric">{{ stats.B.leads }}</td>
                            <td class="highlight-rate">{{ stats.B.click_rate }}</td>
                            <td class="highlight-conv">{{ stats.B.conversion_rate }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="grid">
                <div class="info-box">
                    <h3>Click Rate Formula</h3>
                    <p><strong>Click Rate = (Clicks / Views) × 100</strong><br>
                    Measures top-of-funnel engagement—how effectively each headline and CTA drives clicks.</p>
                </div>
                <div class="info-box">
                    <h3>Conversion Rate Formula</h3>
                    <p><strong>Conversion Rate = (Leads / Views) × 100</strong><br>
                    Measures full-funnel effectiveness—the percentage of visitors who successfully submitted a demo request.</p>
                </div>
                <div class="info-box">
                    <h3>Session De-duplication</h3>
                    <p>Views are counted only once per browser session via <code>sessionStorage</code> to prevent repeat impression skew and React StrictMode double-counting.</p>
                </div>
            </div>

            <div class="footer-links">
                <p>View Raw Data: <a href="/api/results">JSON API (/api/results)</a> | Health Check: <a href="/health">/health</a></p>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_template, stats=stats)

if __name__ == "__main__":
    # Standard port is 5001 as required
    port = int(os.environ.get("PORT", 5001))
    print(f"DemoFlow backend running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
