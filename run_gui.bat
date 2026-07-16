@echo off
title Cairo Metro Depot Agent
echo Starting Depot Agent Dashboard...
echo Opening browser at http://localhost:8501
echo.
echo Press Ctrl+C to stop.
streamlit run app.py --server.port 8501
pause
