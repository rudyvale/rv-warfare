param([string]$Output = (Join-Path (Split-Path -Parent $PSScriptRoot) 'assets'))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Path $Output -Force | Out-Null
$images = @()
foreach ($size in @(16,24,32,48,64,128,256)) {
    $bitmap = [Drawing.Bitmap]::new(512,512)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = 'AntiAlias'
    $path = [Drawing.Drawing2D.GraphicsPath]::new()
    $path.AddArc(20,20,112,112,180,90); $path.AddArc(380,20,112,112,270,90)
    $path.AddArc(380,380,112,112,0,90); $path.AddArc(20,380,112,112,90,90); $path.CloseFigure()
    $brush = [Drawing.Drawing2D.LinearGradientBrush]::new([Drawing.Point]::new(30,30),[Drawing.Point]::new(480,480),[Drawing.Color]::FromArgb(30,45,67),[Drawing.Color]::FromArgb(14,23,38))
    $graphics.FillPath($brush,$path)
    $border = [Drawing.Pen]::new([Drawing.Color]::FromArgb(77,113,137),3)
    $graphics.DrawPath($border,$path)
    $pen = [Drawing.Pen]::new([Drawing.Color]::FromArgb(151,238,214),24)
    $pen.StartCap = 'Round'; $pen.EndCap = 'Round'; $pen.LineJoin = 'Round'
    $graphics.DrawLines($pen,[Drawing.Point[]]@([Drawing.Point]::new(177,184),[Drawing.Point]::new(99,256),[Drawing.Point]::new(177,328)))
    $graphics.DrawLines($pen,[Drawing.Point[]]@([Drawing.Point]::new(335,184),[Drawing.Point]::new(413,256),[Drawing.Point]::new(335,328)))
    $graphics.DrawLine($pen,287,155,225,357)
    $small = [Drawing.Bitmap]::new($size,$size)
    $render = [Drawing.Graphics]::FromImage($small)
    $render.InterpolationMode = 'HighQualityBicubic'
    $render.DrawImage($bitmap,0,0,$size,$size)
    $stream = [IO.MemoryStream]::new()
    $small.Save($stream,[Drawing.Imaging.ImageFormat]::Png)
    $images += [PSCustomObject]@{size=$size;bytes=$stream.ToArray()}
    if ($size -eq 256) { $small.Save((Join-Path $Output 'code.png'),[Drawing.Imaging.ImageFormat]::Png) }
    $stream.Dispose(); $render.Dispose(); $small.Dispose(); $pen.Dispose(); $border.Dispose(); $brush.Dispose(); $path.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
}
$file = [IO.File]::Create((Join-Path $Output 'code.ico'))
$writer = [IO.BinaryWriter]::new($file)
try {
    $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$images.Count)
    $offset = 6 + 16 * $images.Count
    foreach ($entry in $images) {
        $dimension = if ($entry.size -eq 256) {0} else {$entry.size}
        $writer.Write([byte]$dimension); $writer.Write([byte]$dimension); $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([uint16]1); $writer.Write([uint16]32); $writer.Write([uint32]$entry.bytes.Length); $writer.Write([uint32]$offset)
        $offset += $entry.bytes.Length
    }
    foreach ($entry in $images) { $writer.Write([byte[]]$entry.bytes) }
} finally { $writer.Dispose(); $file.Dispose() }
