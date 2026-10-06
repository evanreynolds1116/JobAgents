@echo off
rem Starts the Job Application Assistant and opens http://localhost:8501 once it's ready.
rem Runs from this folder so Streamlit picks up .streamlit\config.toml. Close the window to stop it.
cd /d "%~dp0"
if not exist ".venv\Scripts\streamlit.exe" (
    echo Not installed yet. See README.md, "Install".
    pause
    exit /b 1
)
rem Open the browser after the server has had a few seconds to start.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 5; Start-Process 'http://localhost:8501'"
".venv\Scripts\streamlit.exe" run app.py
