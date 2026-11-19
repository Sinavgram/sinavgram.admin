@echo off
echo Sanal ortam olusturuluyor...
python -m venv venv

echo Sanal ortam aktif ediliyor ve kutuphaneler yukleniyor...
call venv\Scripts\activate

echo Gereksinimler yukleniyor (requirements.txt)...
pip install -r requirements.txt

echo Uygulama baslatiliyor...
python app.py

pause