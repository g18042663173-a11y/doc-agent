[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("deck", "word")]
    [string]$Kind,

    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"
$inputFile = (Resolve-Path -LiteralPath $InputPath).Path
$outputRoot = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$baseName = [System.IO.Path]::GetFileNameWithoutExtension($inputFile)
$report = [ordered]@{
    visual_export_version = "1.0"
    kind = $Kind
    input = [System.IO.Path]::GetFileName($inputFile)
    output_dir = $outputRoot
    pass = $false
    artifacts = [ordered]@{}
}

$office = $null
$document = $null
try {
    if ($Kind -eq "deck") {
        if ([System.IO.Path]::GetExtension($inputFile).ToLowerInvariant() -ne ".pptx") {
            throw "deck 视觉导出只支持 .pptx。"
        }
        $office = New-Object -ComObject PowerPoint.Application
        $document = $office.Presentations.Open($inputFile, $false, $true, $false)
        $pdfPath = Join-Path $outputRoot "$baseName.pdf"
        $pngDirectory = Join-Path $outputRoot "$baseName-png"
        $document.SaveAs($pdfPath, 32)
        $document.SaveAs($pngDirectory, 18)
        $report.artifacts.pdf = [System.IO.Path]::GetFileName($pdfPath)
        $report.artifacts.png_directory = [System.IO.Path]::GetFileName($pngDirectory)
    } else {
        if ([System.IO.Path]::GetExtension($inputFile).ToLowerInvariant() -ne ".docx") {
            throw "word 视觉导出只支持 .docx。"
        }
        $office = New-Object -ComObject Word.Application
        $office.Visible = $false
        $document = $office.Documents.Open($inputFile, $false, $true)
        $pdfPath = Join-Path $outputRoot "$baseName.pdf"
        $document.ExportAsFixedFormat($pdfPath, 17)
        $report.artifacts.pdf = [System.IO.Path]::GetFileName($pdfPath)
    }
    $report.pass = $true
} catch {
    $report.error = "Office 导出失败。请确认本机已安装对应桌面 Office 应用，并在人工验收记录中保留错误详情。"
    $report.exception_type = $_.Exception.GetType().Name
} finally {
    if ($null -ne $document) {
        try { $document.Close() } catch { }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($null -ne $office) {
        try { $office.Quit() } catch { }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($office)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$reportPath = Join-Path $outputRoot "visual_export_report.json"
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding utf8
Write-Output "visual export report: $reportPath"
if (-not $report.pass) { exit 1 }
