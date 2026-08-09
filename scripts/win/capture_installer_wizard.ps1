param(
  [Parameter(Mandatory=$true)][string]$InstallerPath,
  [Parameter(Mandatory=$true)][string]$OutDir
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$sig = @"
using System;
using System.Runtime.InteropServices;
public class Win32W {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
Add-Type -TypeDefinition $sig -ReferencedAssemblies System.Drawing,System.Windows.Forms

function Find-Wizard {
  Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -like "HuaweiDocumentGenerator-Setup*" -and $_.MainWindowHandle -ne 0 } |
    Select-Object -First 1
}
function Capture-Window($proc, [string]$path) {
  [Win32W]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 700
  $rect = New-Object Win32W+RECT
  [Win32W]::GetWindowRect($proc.MainWindowHandle, [ref]$rect) | Out-Null
  $w = $rect.Right - $rect.Left; $h = $rect.Bottom - $rect.Top
  if ($w -le 0 -or $h -le 0) { Write-Output "skip capture (bad rect)"; return }
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp.Size)
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  Write-Output ("captured: " + $proc.MainWindowTitle + " -> " + $path)
}

$proc = Start-Process -FilePath $InstallerPath -PassThru
Start-Sleep -Seconds 5
$wizard = Find-Wizard
if ($null -eq $wizard) { Write-Output "wizard not found"; exit 1 }

$shot = 0
$titles = @{}
for ($i = 0; $i -lt 8; $i++) {
  $wizard = Find-Wizard
  if ($null -eq $wizard) { Write-Output "wizard closed"; break }
  $title = $wizard.MainWindowTitle
  if (-not $titles.ContainsKey($title)) {
    $titles[$title] = $true
    $shot++
    Capture-Window $wizard (Join-Path $OutDir ("wizard-{0:d2}.png" -f $shot))
  }
  # 语言对话框/向导页：Enter = 确定/下一步
  [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
  Start-Sleep -Seconds 2
}

# 到达"准备安装"页后取消，不真正走 UI 安装（功能路径用静默安装验证）
$wizard = Find-Wizard
if ($null -ne $wizard) {
  Capture-Window $wizard (Join-Path $OutDir ("wizard-{0:d2}-before-cancel.png" -f ($shot + 1)))
  [System.Windows.Forms.SendKeys]::SendWait("%{F4}")
  Start-Sleep -Seconds 1
  [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")  # 确认退出安装
  Start-Sleep -Seconds 1
}
$wizard = Find-Wizard
if ($null -eq $wizard) { Write-Output "wizard canceled cleanly" } else { Write-Output "WARNING: wizard still running"; $wizard | Stop-Process -Force }
