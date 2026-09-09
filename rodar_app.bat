@echo off
cd /d "%~dp0"
if not exist venv (
  echo Criando ambiente virtual...
  python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt -q
python -m streamlit run app.py
pause
