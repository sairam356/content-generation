# Installs the free local renderer: Wav2Lip + weights into tools\Wav2Lip (CPU by default).
# Usage:  .\setup\setup-wav2lip.ps1            (CPU torch - works everywhere, ~10x realtime on a laptop i7)
#         .\setup\setup-wav2lip.ps1 -Cuda      (NVIDIA GPU with >= 4 GB VRAM; cu118 wheels)
param([switch]$Cuda)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Dir = Join-Path $Root "tools\Wav2Lip"
New-Item -ItemType Directory -Force (Join-Path $Root "tools") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $Root "assets\me\video") | Out-Null

if (-not (Test-Path (Join-Path $Dir "inference.py"))) {
  Write-Host "[1/4] cloning Wav2Lip" -ForegroundColor Yellow
  git clone --depth 1 https://github.com/Rudrabha/Wav2Lip $Dir
}
$Py = Join-Path $Dir ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
  Write-Host "[2/4] creating venv (Python 3.12)" -ForegroundColor Yellow
  & py -3.12 -m venv (Join-Path $Dir ".venv")
  if ($LASTEXITCODE -ne 0) { & python -m venv (Join-Path $Dir ".venv") }
}
Write-Host "[3/4] installing torch + deps" -ForegroundColor Yellow
& $Py -m pip install -q --upgrade pip
if ($Cuda) { & $Py -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu118 }
else       { & $Py -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu }
& $Py -m pip install -q "numpy<2.3" librosa opencv-python opencv-contrib-python tqdm numba scipy
& python (Join-Path $Root "setup\patch_wav2lip.py") $Dir

Write-Host "[4/4] downloading weights (~520 MB)" -ForegroundColor Yellow
$Ck = Join-Path $Dir "checkpoints\wav2lip_gan.pth"
if (-not (Test-Path $Ck)) {
  Invoke-WebRequest -Uri "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth" -OutFile $Ck
}
$Sfd = Join-Path $Dir "face_detection\detection\sfd\s3fd.pth"
if (-not (Test-Path $Sfd)) {
  Invoke-WebRequest -Uri "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth" -OutFile $Sfd
}
& $Py -c "import torch, librosa, cv2; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
Write-Host "`nWav2Lip ready. Put a 20-30 s video of yourself in assets\me\video\ then: python -m pipeline render <project>" -ForegroundColor Green
