@echo off
cd /d "%~dp0frontend"
npx vitest run --reporter=verbose
