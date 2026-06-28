py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python download_flags.py
Write-Host "Environment ready. Run with: python run.py"
