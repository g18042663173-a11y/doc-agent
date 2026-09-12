param(
    [Parameter(Mandatory=$true)][string]$DeckPath,
    [Parameter(Mandatory=$true)][string]$OutDir
)
$ErrorActionPreference = 'Stop'
$deck = (Resolve-Path -LiteralPath $DeckPath).Path
$out = [IO.Path]::GetFullPath($OutDir)
if (Test-Path -LiteralPath $out) {
    if (@(Get-ChildItem -LiteralPath $out -Force).Count -gt 0) { throw 'Output must be empty.' }
} else { [IO.Directory]::CreateDirectory($out) | Out-Null }
$app = New-Object -ComObject PowerPoint.Application
$presentation = $null
$rows = [Collections.Generic.List[object]]::new()
function Get-TextRecord($shape, [string]$objectPath) {
    if ($shape.HasTextFrame -ne -1 -or $shape.TextFrame2.HasText -ne -1) { return $null }
    $range = $shape.TextFrame2.TextRange
    $lines = [Collections.Generic.List[object]]::new()
    for ($lineIndex=1; $lineIndex -le $range.Lines().Count; $lineIndex++) {
        $line = $range.Lines($lineIndex, 1)
        if (-not [string]::IsNullOrWhiteSpace($line.Text)) {
            $fontSize = [double]$line.Font.Size
            if ($fontSize -le 0) {
                $fontSize = 0
                for ($ch=1; $ch -le $line.Length; $ch++) { $fontSize = [Math]::Max($fontSize, [double]$line.Characters($ch,1).Font.Size) }
            }
            $lines.Add([ordered]@{text=$line.Text; left=[double]$line.BoundLeft; top=[double]$line.BoundTop; width=[double]$line.BoundWidth; height=[double]$line.BoundHeight; font_size_pt=$fontSize})
        }
    }
    return [ordered]@{shape_id=$shape.Id; object_path=$objectPath; text=$range.Text; left=[double]$shape.Left; top=[double]$shape.Top; width=[double]$shape.Width; height=[double]$shape.Height; bound_left=[double]$range.BoundLeft; bound_top=[double]$range.BoundTop; bound_width=[double]$range.BoundWidth; bound_height=[double]$range.BoundHeight; lines=@($lines.ToArray())}
}
function Add-ShapeRecords($shape, [string]$objectPath, $records) {
    if ($shape.Type -eq 6) {
        foreach ($child in $shape.GroupItems) { Add-ShapeRecords $child ($objectPath+'/'+$child.Id) $records }
    } elseif ($shape.HasTable -eq -1) {
        for ($r=1; $r -le $shape.Table.Rows.Count; $r++) {
            for ($c=1; $c -le $shape.Table.Columns.Count; $c++) {
                $cell = $shape.Table.Cell($r,$c).Shape
                $record = Get-TextRecord $cell ($objectPath+'/r'+$r+'c'+$c)
                if ($null -ne $record) {
                    # Office cell text ranges report local coordinates, with a zero-height
                    # origin even when vertically centered. Normalize to the slide.
                    $dx = [double]$cell.Left
                    $dy = [double]$cell.Top
                    if ($cell.TextFrame2.VerticalAnchor -eq 3) { $dy += [double]$cell.Height / 2 }
                    elseif ($cell.TextFrame2.VerticalAnchor -eq 4) { $dy += [double]$cell.Height }
                    $record['bound_left'] += $dx
                    $record['bound_top'] += $dy
                    foreach ($line in $record['lines']) { $line['left'] += $dx; $line['top'] += $dy }
                    $record['coordinate_normalization'] = 'office_cell_local_to_slide'
                    $records.Add($record)
                }
            }
        }
    } else {
        $record = Get-TextRecord $shape $objectPath
        if ($null -ne $record) { $records.Add($record) }
    }
}
try {
    $presentation = $app.Presentations.Open($deck, $true, $false, $false)
    $width = 1920
    $height = [int]($width * $presentation.PageSetup.SlideHeight / $presentation.PageSetup.SlideWidth)
    for ($index=1; $index -le $presentation.Slides.Count; $index++) {
        $slide = $presentation.Slides.Item($index)
        $png = Join-Path $out ('p{0:d2}.png' -f $index)
        $slide.Export($png, 'PNG', $width, $height)
        $textRows = [Collections.Generic.List[object]]::new()
        foreach ($shape in $slide.Shapes) {
            Add-ShapeRecords $shape ([string]$shape.Id) $textRows
        }
        $rows.Add([ordered]@{page_id=('p{0:d2}' -f $index); png=$png; png_sha256=(Get-FileHash -LiteralPath $png -Algorithm SHA256).Hash.ToLowerInvariant(); text_bounds=@($textRows.ToArray())})
    }
    # pass describes successful export only. It must never stand in for visual acceptance.
    $report = [ordered]@{format='rdw_office_export'; version='2.1'; pass=$true; pass_scope='office_export_only'; visual_acceptance='pending'; measurement_scope='slide_text_groups_and_table_cells; chart_labels_and_master_assets_require_visual_review'; office_version=$app.Version; artifact_sha256=(Get-FileHash -LiteralPath $deck -Algorithm SHA256).Hash.ToLowerInvariant(); page_count=$presentation.Slides.Count; pages=@($rows.ToArray())}
    [IO.File]::WriteAllText((Join-Path $out 'office_export.json'), ($report | ConvertTo-Json -Depth 14), [Text.UTF8Encoding]::new($false))
    Write-Output ('Exported {0} pages at {1}x{2}' -f $presentation.Slides.Count,$width,$height)
} finally {
    if ($null -ne $presentation) { $presentation.Close(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($presentation) }
    # PowerPoint shares its COM application with other user/agent presentations.
    # Close only our presentation, never terminate that shared application.
    if ($null -ne $app) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) }
}
