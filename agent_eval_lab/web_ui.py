from flask import Flask, render_template
from pathlib import Path
import json
from datetime import datetime

RUNS_DIR = Path("runs")

def run_app(host='0.0.0.0', port=5000):
    """Run the Flask web UI."""
    app = Flask(__name__, template_folder=str(Path(__file__).parent / 'templates'))

    @app.route("/")
    def index():
        # List all JSON result files sorted by modification time (newest first)
        if not RUNS_DIR.exists():
            runs = []
        else:
            files = sorted(RUNS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            runs = []
            for f in files:
                try:
                    with open(f) as fp:
                        data = json.load(fp)
                    mtime = f.stat().st_mtime
                    timestamp_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    # Extract summary fields
                    run = {
                        "filename": f.name,
                        "timestamp_str": timestamp_str,
                        "average_score": data.get("average_score"),
                        "agent_pass_rate": data.get("agent_pass_rate_percent"),
                        "execution_pass_rate": data.get("execution_pass_rate_percent"),
                        "total_items": data.get("total_items"),
                        "average_coverage": data.get("average_coverage_percent"),
                    }
                    runs.append(run)
                except Exception:
                    # Skip invalid or unreadable files
                    continue
        return render_template("index.html", runs=runs)

    @app.route("/run/<filename>")
    def run_detail(filename):
        path = RUNS_DIR / filename
        if not path.exists():
            return "Not found", 404
        try:
            with open(path) as fp:
                data = json.load(fp)
        except Exception:
            return "Error reading file", 500
        return render_template("run_detail.html", summary=data, filename=filename)

    app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    run_app()
