param(
  [Parameter(Mandatory=$true)][string]$ProcessName,
  [Parameter(Mandatory=$true)][string]$OutPng,
  [int]$WaitSeconds = 6
)
Add-Type -AssemblyName System.Drawing
$proc = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "$ProcessName*" -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($null -eq $proc) { Start-Sleep -Seconds $WaitSeconds; $proc = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "$ProcessName*" -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1 }
if ($null -eq $proc) { Write-Output "no window found for $ProcessName"; exit 1 }
$sig = @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll", SetLastError=true)] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll", SetLastError=true)] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint flags);
  [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr dpiContext);
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
Add-Type -TypeDefinition $sig -ReferencedAssemblies System.Drawing
$previousDpiContext = [Win32]::SetThreadDpiAwarenessContext([IntPtr](-4))
try {
  [Win32]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 800
  $rect = New-Object Win32+RECT
  if (-not [Win32]::GetWindowRect($proc.MainWindowHandle, [ref]$rect)) { throw "无法读取窗口边界。" }
  $w = $rect.Right - $rect.Left; $h = $rect.Bottom - $rect.Top
  if ($w -le 0 -or $h -le 0) { throw "窗口边界无效：${w}x${h}" }
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  try {
    if (-not [Win32]::PrintWindow($proc.MainWindowHandle, $hdc, 2)) { throw "PrintWindow 采集失败。" }
  } finally {
    $g.ReleaseHdc($hdc)
  }
  $bmp.Save($OutPng, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
} finally {
  if ($previousDpiContext -ne [IntPtr]::Zero) { [Win32]::SetThreadDpiAwarenessContext($previousDpiContext) | Out-Null }
}
Write-Output "captured $($proc.MainWindowTitle) ${w}x${h} -> $OutPng"
