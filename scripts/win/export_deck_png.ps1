param(
  [Parameter(Mandatory=$true)][string]$DeckPath,
  [Parameter(Mandatory=$true)][string]$OutDir
)
$ErrorActionPreference = "Stop"
$deck = (Resolve-Path $DeckPath).Path
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$out = (Resolve-Path $OutDir).Path

$app = New-Object -ComObject PowerPoint.Application
try {
  $pres = $app.Presentations.Open($deck, $true, $false, $false)  # ReadOnly, Untitled, WithWindow=false
  try {
    $w = 1600
    $h = [int](1600 * $pres.PageSetup.SlideHeight / $pres.PageSetup.SlideWidth)
    for ($i = 1; $i -le $pres.Slides.Count; $i++) {
      $png = Join-Path $out ("slide-{0:d2}.png" -f $i)
      $pres.Slides.Item($i).Export($png, "PNG", $w, $h)
    }
    Write-Output ("exported {0} slides at {1}x{2} -> {3}" -f $pres.Slides.Count, $w, $h, $out)
  } finally {
    $pres.Close()
  }
} finally {
  $app.Quit()
}
