import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    """Launch the Streamlit frontend application."""
    print("Starting Streamlit frontend on port 8501...")
    app_file = str(PROJECT_ROOT / "frontend" / "app.py")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_file,
        "--server.port",
        "8501",
        "--server.headless",
        "true",
    ]
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nStopping frontend...")


if __name__ == "__main__":
    main()
