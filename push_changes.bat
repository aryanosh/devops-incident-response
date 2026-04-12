@echo off
REM Git commit and push script for DevOps Incident Response submission

echo ============================================================
echo PUSHING CHANGES TO GITHUB AND HUGGINGFACE
echo ============================================================
echo.

cd /d C:\Users\aryan\Documents\projects\devops_incident_env

echo [1/5] Checking git status...
git status
echo.

echo [2/5] Adding all changes...
git add .
echo.

echo [3/5] Committing changes...
git commit -m "Align repo with DevOps Incident Response template" -m "" -m "- Rebuilt the environment around the template's 3-task manual FastAPI structure" -m "- Added root requirements, task catalog, grader, baseline, and server/environment modules" -m "- Switched serving and Docker defaults to port 7860" -m "- Updated inference.py to use remote HTTP first, local TestClient fallback, and heuristic fallback" -m "- Verified python -m pytest, openenv validate, and local inference output"
echo.

echo [4/5] Pushing to GitHub...
git push origin main
echo.

echo [5/5] Verifying push...
git log --oneline -1
echo.

echo ============================================================
echo PUSH COMPLETE!
echo ============================================================
echo.
echo Your changes have been pushed to:
echo - GitHub: https://github.com/aryanosh/devops-incident-response
echo - HuggingFace will auto-sync in 5-10 minutes
echo.
echo Next: Wait for HF Space to rebuild, then submit!
echo ============================================================

pause
