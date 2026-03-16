"""
Instala todas as dependências necessárias.
Execute uma vez antes de rodar o painel:  python install.py
"""
import subprocess, sys

pacotes = [
    "streamlit>=1.32.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "python-dateutil>=2.8.0",
    "plotly>=5.18.0",
    "openpyxl>=3.1.0",
]

print("Instalando dependências do Budget Engine...")
for p in pacotes:
    print(f"  → {p}")
    subprocess.run([sys.executable, "-m", "pip", "install", p], check=True, capture_output=True)

print("\n✅ Tudo instalado! Para rodar o painel execute:")
print("   python run.py")
print("   ou: streamlit run ui/app.py")
