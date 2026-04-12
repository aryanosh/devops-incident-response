# Git Push Script for DevOps Incident Response Submission
# Run this in PowerShell to push all changes

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PUSHING CHANGES TO GITHUB AND HUGGINGFACE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location C:\Users\aryan\Documents\projects\devops_incident_env

Write-Host "[1/5] Checking git status..." -ForegroundColor Yellow
git status
Write-Host ""

Write-Host "[2/5] Adding all changes..." -ForegroundColor Yellow
git add .
Write-Host ""

Write-Host "[3/5] Committing changes..." -ForegroundColor Yellow
git commit -m "Align repo with DevOps Incident Response template" -m "" -m "- Rebuilt the environment around the template's 3-task manual FastAPI structure" -m "- Added root requirements, task catalog, grader, baseline, and server/environment modules" -m "- Switched serving and Docker defaults to port 7860" -m "- Updated inference.py to use remote HTTP first, local TestClient fallback, and heuristic fallback" -m "- Verified python -m pytest, openenv validate, and local inference output"
Write-Host ""

Write-Host "[4/5] Pushing to GitHub..." -ForegroundColor Yellow
git push origin main
Write-Host ""

Write-Host "[5/5] Verifying push..." -ForegroundColor Yellow
git log --oneline -1
Write-Host ""

Write-Host "============================================================" -ForegroundColor Green
Write-Host "PUSH COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your changes have been pushed to:" -ForegroundColor White
Write-Host "- GitHub: https://github.com/aryanosh/devops-incident-response" -ForegroundColor Cyan
Write-Host "- HuggingFace will auto-sync in 5-10 minutes" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next: Wait for HF Space to rebuild, then submit!" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
