# Watch Firefox + Simplify Copilot. Never open Resume Builder / Tailor Resume. Click Autofill, Create account,
# Continue, Start, and Submit by meaning (names vary). Never mouse. Never minimize.
# Do not click page-level Apply. Sidebar Copilot first; form Continue/Next/Submit allowed.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$rootDir = 'C:\Users\MohammedAhmed\hyderabad-job-applications'
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker

$actionSpecs = @(
  @{ Re = 'autofill this (page|form)|auto-fill this (page|form)'; Pri = 90; Where = 'side'; Once = $true }
  @{ Re = 'autofill with resume|fill with resume'; Pri = 88; Where = 'side'; Once = $true }
  @{ Re = 'create account|create account.*(auto)?fill|sign up (to|&|and)|register.*(auto)?fill'; Pri = 86; Where = 'side'; Once = $true }
  @{ Re = 'log in to autofill|sign in (to |and )?(autofill|simplify)|login to autofill'; Pri = 84; Where = 'side'; Once = $true }
  @{ Re = 'continue with application|continue to (the )?application|accept and continue'; Pri = 82; Where = 'side'; Once = $false }
  @{ Re = 'save and continue|save & continue|next step|continue to next'; Pri = 78; Where = 'any'; Once = $false }
  @{ Re = '^(continue|next)$'; Pri = 74; Where = 'any'; Once = $false }
  @{ Re = 'start appl(y|ication)|start applying'; Pri = 70; Where = 'side'; Once = $true }
  @{ Re = 'review and submit|review & submit|submit application|submit your application|^submit$'; Pri = 60; Where = 'any'; Once = $true }
  @{ Re = 'run autofill again|autofill again'; Pri = 40; Where = 'side'; Once = $true }
)

$doneRe = 'application submitted|application received|already applied|you applied for this job|we submitted your application|successfully submitted|applied with simplify'
$skipRe = 'tailor|resume builder|generate tailor|create tailored|use this resume|enable ai|request autofill|hide until|cover letter|unlimited resume|upgrade|pricing|learn more|easy apply|^apply$|apply now|apply for this|minimize|restore|close|bookmark|extensions|reader view|new tab|list all tabs|account$|firefox$|open menu|zoom'

function Get-FirefoxWindow {
  $root = [System.Windows.Automation.AutomationElement]::RootElement
  $cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ClassNameProperty, 'MozillaWindowClass')
  $wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
  $best = $null
  $bestArea = 0
  for ($i = 0; $i -lt $wins.Count; $i++) {
    $w = $wins.Item($i)
    $r = $w.Current.BoundingRectangle
    $area = [Math]::Max(0, $r.Width) * [Math]::Max(0, $r.Height)
    if ($area -gt $bestArea) { $best = $w; $bestArea = $area }
  }
  return $best
}

function Page-Loading([string]$title) {
  $t = ($title + '').ToLower()
  if (-not $t -or $t -eq 'mozilla firefox') { return $true }
  if ($t -match 'just a moment|please wait|^loading|new tab|about:blank|restore session|resume builder') { return $true }
  return $false
}

function Get-Label($el) {
  try {
    $parts = @(
      $el.Current.Name,
      $el.Current.HelpText,
      $el.Current.AutomationId
    )
    try {
      $val = $el.GetCurrentPropertyValue([System.Windows.Automation.ValuePattern]::ValueProperty)
      if ($val) { $parts += [string]$val }
    } catch {}
    return (($parts -join ' ') -replace '\s+', ' ').Trim()
  } catch { return '' }
}

function Test-Invokable($el) {
  try {
    $p = $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    return [bool]$p
  } catch { return $false }
}

function Invoke-Ready($el) {
  try {
    $inv = $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    if ($inv) { $inv.Invoke(); return $true }
  } catch {}
  try {
    $acc = $el.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern)
    if ($acc) { $acc.DoDefaultAction(); return $true }
  } catch {}
  return $false
}

function Collect-Right($win, [double]$sideX, [double]$formLeft, [int]$minY, [int]$maxNodes) {
  $found = New-Object System.Collections.Generic.List[object]
  $stack = New-Object System.Collections.Stack
  $stack.Push(@($win, 0))
  $n = 0
  while ($stack.Count -gt 0 -and $n -lt $maxNodes) {
    $pair = $stack.Pop()
    $el = $pair[0]
    $depth = [int]$pair[1]
    $n++
    if ($depth -gt 22) { continue }
    $r = $null
    try { $r = $el.Current.BoundingRectangle } catch { continue }
    if ($r.Width -le 0 -or $r.Height -le 0) { }
    elseif (($r.X + $r.Width) -lt $formLeft -and $depth -gt 2) { continue }
    try {
      $label = Get-Label $el
      $enabled = $el.Current.IsEnabled
      $inv = Test-Invokable $el
      if ($label -and $label.Length -lt 100 -and ($inv -or $enabled)) {
        if ($r.Height -ge 10 -and $r.Width -ge 20 -and $r.Y -ge $minY) {
          $found.Add([pscustomobject]@{
            El = $el; Name = $label; X = $r.X; Y = $r.Y
            Enabled = $enabled; Invokable = $inv; Side = ($r.X -ge $sideX)
          })
        }
      }
    } catch {}
    if ($depth -ge 22) { continue }
    try {
      $child = $walker.GetFirstChild($el)
      $kids = @()
      $k = 0
      while ($child -and $k -lt 40) {
        $kids += $child
        $child = $walker.GetNextSibling($child)
        $k++
      }
      for ($i = $kids.Count - 1; $i -ge 0; $i--) {
        $stack.Push(@($kids[$i], ($depth + 1)))
      }
    } catch {}
  }
  return $found
}

function Find-Exact($win, [string]$name, [double]$minX, [int]$minY) {
  $cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::NameProperty, $name)
  $els = $null
  try { $els = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond) } catch { return $null }
  if (-not $els) { return $null }
  for ($i = 0; $i -lt $els.Count; $i++) {
    $el = $els.Item($i)
    try {
      if (-not $el.Current.IsEnabled) { continue }
      $r = $el.Current.BoundingRectangle
      if ($r.Height -lt 10 -or $r.Width -lt 18) { continue }
      if ($r.Y -lt $minY) { continue }
      if ($minX -gt 0 -and $r.X -lt $minX) { continue }
      return $el
    } catch { continue }
  }
  return $null
}

function Pick-Action($items, [double]$sideX, $clicked, [string]$title) {
  $best = $null
  $bestPri = -1
  foreach ($it in $items) {
    $name = ($it.Name + '')
    $low = $name.ToLower()
    if ($low -match $skipRe) { continue }
    if (-not $it.Enabled -and -not $it.Invokable) { continue }
    foreach ($spec in $actionSpecs) {
      if ($low -notmatch $spec.Re) { continue }
      if ($spec.Where -eq 'side' -and -not $it.Side -and $it.X -lt $sideX) { continue }
      $key = $title + '|' + $spec.Re + '|' + $low.Substring(0, [Math]::Min(40, $low.Length))
      if ($spec.Once -and $clicked.Contains($key)) { continue }
      if ([int]$spec.Pri -gt $bestPri) {
        $best = [pscustomobject]@{ Item = $it; Spec = $spec; Key = $key; Label = $name }
        $bestPri = [int]$spec.Pri
      }
    }
  }
  return $best
}

Write-Output 'Simplify watch: Autofill, Create account, Continue, Start, Submit. Resume Builder / Tailor Resume disabled.'
$end = (Get-Date).AddSeconds(10800)
$lastTitle = ''
$readyAt = Get-Date '2000-01-01'
$clicked = New-Object 'System.Collections.Generic.HashSet[string]'
$handledSubmit = New-Object 'System.Collections.Generic.HashSet[string]'
$lastDump = Get-Date '2000-01-01'
$panelTried = $false
$exactNames = @(
  'Autofill this page', 'Autofill This Page', 'Autofill with Resume',
  'Create Account & Autofill', 'Create account',
  'Continue with application', 'Accept and Continue', 'Continue', 'Next',
  'Start application', 'Start Application',
  'Submit application', 'Submit Application', 'Submit',
  'Run Autofill Again'
)

while ((Get-Date) -lt $end) {
  $win = Get-FirefoxWindow
  if (-not $win) { Start-Sleep -Seconds 3; continue }
  $title = ''
  try { $title = [string]$win.Current.Name } catch {}
  $wr = $win.Current.BoundingRectangle
  $sideX = [Math]::Max(820, $wr.X + ($wr.Width * 0.56))
  $formLeft = $wr.X + ($wr.Width * 0.18)

  if ($title -ne $lastTitle) {
    $lastTitle = $title
    $clicked.Clear()
    $readyAt = (Get-Date).AddSeconds(5)
    $panelTried = $false
    Write-Output ('  Page: {0}' -f $title.Substring(0, [Math]::Min(100, $title.Length)))
    Start-Sleep -Seconds 1
    continue
  }
  if (Page-Loading $title) { Start-Sleep -Seconds 2; continue }

  $titleDone = ($title.ToLower() -match 'thanks|confirmation|application submitted')
  if ($titleDone -and -not $handledSubmit.Contains($title)) {
    Write-Output '  SUBMIT recorded from window title.'
    [void]$handledSubmit.Add($title)
    & python (Join-Path $rootDir 'auto_next.py') $title
    $readyAt = (Get-Date).AddSeconds(10)
    Start-Sleep -Seconds 5
    continue
  }

  if ((Get-Date) -lt $readyAt) { Start-Sleep -Milliseconds 800; continue }

  if (-not $panelTried) {
    $panel = Find-Exact $win 'Simplify Copilot' ($wr.X + $wr.Width * 0.55) 30
    if ($panel -and (Invoke-Ready $panel)) {
      Write-Output '  Opened Simplify Copilot panel.'
      Start-Sleep -Seconds 2
    }
    $panelTried = $true
  }

  $hits = New-Object System.Collections.Generic.List[object]
  foreach ($name in $exactNames) {
    $el = Find-Exact $win $name 0 60
    if (-not $el) { continue }
    try {
      $r = $el.Current.BoundingRectangle
      $hits.Add([pscustomobject]@{
        El = $el; Name = $name; X = $r.X; Y = $r.Y
        Enabled = $el.Current.IsEnabled; Invokable = $true; Side = ($r.X -ge ($sideX - 80))
      })
    } catch {}
  }

  $walked = Collect-Right $win $sideX $formLeft 70 700
  foreach ($w in $walked) { $hits.Add($w) }

  $doneHit = $null
  foreach ($it in $walked) {
    if (($it.Name + '').ToLower() -match $doneRe) { $doneHit = $it; break }
  }
  if ($doneHit -and -not $handledSubmit.Contains($title)) {
    Write-Output ('  SUBMIT recorded: {0}' -f $doneHit.Name)
    [void]$handledSubmit.Add($title)
    & python (Join-Path $rootDir 'auto_next.py') $title
    $readyAt = (Get-Date).AddSeconds(10)
    Start-Sleep -Seconds 5
    continue
  }

  $pick = Pick-Action $hits $sideX $clicked $title
  if ($pick -and (Invoke-Ready $pick.Item.El)) {
    [void]$clicked.Add($pick.Key)
    Write-Output ('  Clicked Simplify/form: {0}' -f $pick.Label)
    if ($pick.Label -match 'submit') {
      Start-Sleep -Seconds 5
      if (-not $handledSubmit.Contains($title)) {
        [void]$handledSubmit.Add($title)
        Write-Output '  SUBMIT recorded after Submit click.'
        & python (Join-Path $rootDir 'auto_next.py') $title
      }
      $readyAt = (Get-Date).AddSeconds(10)
    } else {
      $readyAt = (Get-Date).AddSeconds(5)
    }
    Start-Sleep -Seconds 4
    continue
  }

    $panel = Find-Exact $win 'Simplify Copilot' 0 20
    if ($panel -and (((Get-Date) - $lastDump).TotalSeconds -ge 18)) {
      if (Invoke-Ready $panel) { Write-Output '  Re-opened Simplify Copilot.' }
    }
    if (((Get-Date) - $lastDump).TotalSeconds -ge 20) {
    $useful = @()
    foreach ($it in $walked) {
      $low = ($it.Name + '').ToLower()
      if ($low -match $skipRe) { continue }
      if ($it.Side -or $low -match 'autofill|continue|submit|account|next|start appl') {
        $useful += ($it.Name.Substring(0, [Math]::Min(48, $it.Name.Length)))
      }
    }
    $useful = $useful | Select-Object -Unique | Select-Object -First 14
    if ($useful.Count -gt 0) {
      Write-Output ('  Visible actions: {0}' -f ($useful -join ' | '))
    } else {
      Write-Output '  Watching Simplify + form for the next action.'
    }
    $lastDump = Get-Date
  }
  Start-Sleep -Seconds 2
}
Write-Output '  Watch ended.'
