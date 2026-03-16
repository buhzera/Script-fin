"""
Atalho para rodar o painel direto com: python run.py
Abre o navegador automaticamente em http://localhost:8501
"""
import subprocess, sys, os, time, threading, webbrowser

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def _abrir_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:8501")

threading.Thread(target=_abrir_browser, daemon=True).start()

subprocess.run([sys.executable, "-m", "streamlit", "run", "ui/app.py"], check=True)
