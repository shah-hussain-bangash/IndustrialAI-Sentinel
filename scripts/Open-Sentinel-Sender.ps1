param(
    [string]$ProjectPath = 'C:\industrialai-sentinel',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'

function Get-SentinelKeyCheck {
    param([string]$Value)
    $text = $Value.Trim()
    $valid = $text -cmatch '^sgw\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[A-Za-z0-9_-]{43}$'
    if ($valid) { $reason = 'Gateway key loaded: 84 characters. Click Send sample.' }
    elseif ($text.Length -eq 0) { $reason = 'No key loaded. Copy the gateway credential from Sentinel.' }
    elseif (-not $text.StartsWith('sgw.')) { $reason = "Copied text has $($text.Length) characters and does not begin with sgw. In Sentinel use Show credential, select the key and copy it manually." }
    elseif ($text.Length -ne 84) { $reason = "Key is incomplete or has extra text: $($text.Length) characters; expected 84. Select only the full gateway key in Sentinel and copy again." }
    else { $reason = 'Key has an invalid format. In Sentinel use Show credential and copy the full key only.' }
    return [pscustomobject]@{Valid=[bool]$valid; Length=$text.Length; Message=$reason}
}

function Invoke-SentinelSampleWindowSender {
    param([string]$PythonPath, [string]$SenderPath, [string]$Credential)
    $encodedPath = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($SenderPath))
    $pythonCode = "import base64,getpass,runpy,sys; getpass.getpass=lambda prompt='': sys.stdin.read().strip(); runpy.run_path(base64.b64decode('$encodedPath').decode('utf-8'),run_name='__main__')"
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $PythonPath
    $start.Arguments = '-I -B -c "' + $pythonCode + '"'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    try {
        $null = $process.Start()
        $outputTask = $process.StandardOutput.ReadToEndAsync()
        $errorTask = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.Write($Credential)
        $process.StandardInput.Close()
        if (-not $process.WaitForExit(60000)) {
            $process.Kill()
            throw 'Sender timed out. Check Sentinel before submitting another sample.'
        }
        $output = $outputTask.GetAwaiter().GetResult()
        $null = $errorTask.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw 'Sample could not be confirmed. Keep Sentinel running and check that this is its latest gateway credential.' }
        $match = [regex]::Match($output, '(?s)\{.*?\}')
        if (-not $match.Success) { throw 'The sender returned an unexpected result.' }
        $result = $match.Value | ConvertFrom-Json
        if ($null -eq $result.inserted -or $null -eq $result.duplicates) { throw 'The sender returned an unexpected result.' }
        return [pscustomobject]@{Inserted=[int]$result.inserted; Duplicates=[int]$result.duplicates}
    } finally {
        $process.Dispose()
    }
}

$python = Join-Path $ProjectPath '.venv\Scripts\python.exe'
$sender = Join-Path $ProjectPath 'scripts\send_gateway_sample.py'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $sender)) {
    throw 'The project Python or sender script is missing. Use the existing Sentinel project path.'
}
if ($CheckOnly) { Write-Output 'SENDER_WINDOW_PREFLIGHT=PASS'; return }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object Windows.Forms.Form
$form.Text = 'Sentinel - Send a sensor sample (v2)'
$form.ClientSize = New-Object Drawing.Size(660,330)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object Drawing.Font('Segoe UI',10)
$help = New-Object Windows.Forms.Label
$help.Text = "Keep Sentinel running. In Sentinel click Copy credential, then return here.`r`nClick Paste copied key, followed by Send sample."
$help.SetBounds(20,20,620,55)
$keyBox = New-Object Windows.Forms.TextBox
$keyBox.UseSystemPasswordChar = $true
$keyBox.SetBounds(20,85,620,30)
$paste = New-Object Windows.Forms.Button
$paste.Text = 'Paste copied key'
$paste.SetBounds(20,130,180,38)
$send = New-Object Windows.Forms.Button
$send.Text = 'Send sample'
$send.SetBounds(215,130,180,38)
$send.Enabled = $false
$status = New-Object Windows.Forms.Label
$status.SetBounds(20,185,620,120)
$status.Text = 'The key stays masked and is passed to Python in memory.'
$keyBox.Add_TextChanged({
    $check = Get-SentinelKeyCheck -Value $keyBox.Text
    $send.Enabled = $check.Valid
    $status.Text = $check.Message
})
$paste.Add_Click({
    try {
        if (-not [Windows.Forms.Clipboard]::ContainsText()) { $status.Text = 'Clipboard has no text. Copy the gateway credential from Sentinel first.'; return }
        $copied = [Windows.Forms.Clipboard]::GetText().Trim()
        $check = Get-SentinelKeyCheck -Value $copied
        $keyBox.Text = $copied
        $send.Enabled = $check.Valid
        $status.Text = $check.Message
        $copied = $null
    } catch { $status.Text = 'Clipboard is busy. Click Paste copied key again.' }
})
$send.Add_Click({
    $check = Get-SentinelKeyCheck -Value $keyBox.Text
    if (-not $check.Valid) { $status.Text = $check.Message; return }
    $send.Enabled = $false
    $paste.Enabled = $false
    $status.Text = 'Sending sample...'
    $form.Refresh()
    try {
        $result = Invoke-SentinelSampleWindowSender -PythonPath $python -SenderPath $sender -Credential $keyBox.Text.Trim()
        $keyBox.Clear()
        $keyBox.Enabled = $false
        $status.Text = "Success: $($result.Inserted) inserted events, $($result.Duplicates) duplicates.`r`nIn Sentinel click Refresh gateways. Snapshot publication remains a separate review."
    } catch {
        $keyBox.Clear()
        $paste.Enabled = $true
        $status.Text = $_.Exception.Message
    }
})
$form.Add_FormClosed({ $keyBox.Clear() })
$form.Controls.AddRange(@($help,$keyBox,$paste,$send,$status))
$null = $form.ShowDialog()
$form.Dispose()
