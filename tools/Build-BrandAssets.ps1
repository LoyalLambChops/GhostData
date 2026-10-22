# Original GhostData mark. Vector geometry is rendered locally; no downloaded assets.
# Run on Windows to regenerate the committed PNG and multi-resolution ICO.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$assets = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\app\GhostData.App\Assets'))
New-Item -ItemType Directory -Force -Path $assets | Out-Null
$frames = @()
foreach ($size in @(16,20,24,32,40,48,64,128,256)) {
    $bitmap = [Drawing.Bitmap]::new($size*4,$size*4)
    $g = [Drawing.Graphics]::FromImage($bitmap)
    $g.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.ScaleTransform($size*4/256.0,$size*4/256.0)
    $navy = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml('#0B1520'))
    $white = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml('#F2F7FA'))
    $cyan = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml('#42E2FF'))
    $tile = [Drawing.Drawing2D.GraphicsPath]::new()
    $tile.AddArc(4,4,64,64,180,90); $tile.AddArc(188,4,64,64,270,90)
    $tile.AddArc(188,188,64,64,0,90); $tile.AddArc(4,188,64,64,90,90); $tile.CloseFigure()
    $g.FillPath($navy,$tile)
    $ghost = [Drawing.Drawing2D.GraphicsPath]::new()
    $ghost.AddBezier(55,209,55,174,55,137,55,109)
    $ghost.AddBezier(55,109,55,65,85,38,128,38)
    $ghost.AddBezier(128,38,171,38,201,65,201,109)
    $ghost.AddLine(201,109,201,209)
    $ghost.AddBezier(201,209,187,209,182,193,170,193)
    $ghost.AddBezier(170,193,154,193,148,215,128,215)
    $ghost.AddBezier(128,215,108,215,102,193,86,193)
    $ghost.AddBezier(86,193,74,193,69,209,55,209); $ghost.CloseFigure()
    $g.FillPath($white,$ghost)
    $g.FillEllipse($navy,85,86,24,28); $g.FillEllipse($navy,147,86,24,28)
    $g.FillRectangle($navy,81,131,94,48)
    $g.FillRectangle($cyan,87,155,20,18)
    $g.FillRectangle($cyan,118,145,20,28)
    $g.FillRectangle($cyan,149,135,20,38)
    $small = [Drawing.Bitmap]::new($size,$size)
    $sg = [Drawing.Graphics]::FromImage($small)
    $sg.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $sg.DrawImage($bitmap,0,0,$size,$size)
    $stream = [IO.MemoryStream]::new()
    $small.Save($stream,[Drawing.Imaging.ImageFormat]::Png)
    $frames += ,@{ Size=$size; Bytes=$stream.ToArray() }
    if ($size -eq 256) { $small.Save((Join-Path $assets 'GhostData.png'),[Drawing.Imaging.ImageFormat]::Png) }
    $stream.Dispose(); $sg.Dispose(); $small.Dispose(); $ghost.Dispose(); $tile.Dispose()
    $navy.Dispose(); $white.Dispose(); $cyan.Dispose(); $g.Dispose(); $bitmap.Dispose()
}
$file = [IO.File]::Create((Join-Path $assets 'GhostData.ico'))
$writer = [IO.BinaryWriter]::new($file)
try {
    $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$frames.Count)
    $offset = 6 + 16 * $frames.Count
    foreach ($frame in $frames) {
        $dimension = if ($frame.Size -eq 256) { 0 } else { $frame.Size }
        $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
        $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([uint16]1); $writer.Write([uint16]32)
        $writer.Write([uint32]$frame.Bytes.Length); $writer.Write([uint32]$offset)
        $offset += $frame.Bytes.Length
    }
    foreach ($frame in $frames) { $writer.Write([byte[]]$frame.Bytes) }
} finally { $writer.Dispose(); $file.Dispose() }
