@echo off
cd /d "%~dp0"
rem Try to run using conda if available
where conda >nul 2>&1
if %ERRORLEVEL%==0 (
	echo Launching SQLify via conda run -n nosql...
	conda run -n nosql python app.py
	goto :eof
)

rem Try common Miniconda/Anaconda install location
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
	echo Launching SQLify via %USERPROFILE%\miniconda3\Scripts\conda.exe run -n nosql...
	"%USERPROFILE%\miniconda3\Scripts\conda.exe" run -n nosql python app.py
	goto :eof
)

rem Fallback to any project venvs we've used
if exist "%~dp0.venv_pyside\Scripts\python.exe" (
	"%~dp0.venv_pyside\Scripts\python.exe" app.py
	goto :eof
)
if exist "%~dp0.venv\Scripts\python.exe" (
	"%~dp0.venv\Scripts\python.exe" app.py
	goto :eof
)
if exist "%~dp0.venv_pyside\bin\python.exe" (
	"%~dp0.venv_pyside\bin\python.exe" app.py
	goto :eof
)
if exist "%~dp0.venv\bin\python.exe" (
	"%~dp0.venv\bin\python.exe" app.py
	goto :eof
)

echo No suitable Python/Conda found to launch SQLify.
echo Run create_conda_env.ps1 or setup_venv_pyside6.ps1 to prepare an environment.
pause
