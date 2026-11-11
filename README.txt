SMART WASTE MANAGEMENT - RUN INSTRUCTIONS

1. Install Python 3.10 or newer.
2. Extract this folder.
3. Open Command Prompt / PowerShell in this folder.
4. Create and activate a virtual environment (recommended):
   python -m venv venv
   Windows: venv\Scripts\activate
5. Install dependencies:
   python -m pip install -r requirements.txt
6. Run:
   streamlit run app.py
7. Open the local URL printed by Streamlit (usually http://localhost:8501).

DEMO LOGINS
User: user / user123
Municipality: municipal / muni123
Admin: admin / admin123

NOTES
- The SQLite database (waste_management.db) and uploads folder are created beside app.py.
- Keep the database and uploads folder together with app.py after creating them.
- Photo screening can flag exact/similar images for manual review. It cannot prove a photo is genuine or fake.
- Truck tracking displays the latest GPS point saved by the driver/device. Continuous background live tracking needs a separately deployed driver-phone GPS update service; this Streamlit demo does not provide background tracking.
- GPS browser access requires permission and generally HTTPS or localhost.
- Change demo passwords before deploying. This is a demonstration project, not production-secure authentication.
