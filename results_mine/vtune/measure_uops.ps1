# Part 4: micro-op counts with VTune (counting mode). Must run as administrator.
#   powershell -NoProfile -ExecutionPolicy Bypass -File measure_uops.ps1 [-ProbeOnly]
# Writes everything into this folder: probe.log, run.log, raw\<cpu>_<kernel>_r<rep>.csv
param([switch]$ProbeOnly)
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $here '..\..\harness\uopcount.exe' | Resolve-Path
$vt = 'C:\Program Files (x86)\Intel\oneAPI\vtune\2026.6\bin64\vtune.exe'
$work = Join-Path $env:TEMP 'lea_vtune_results'   # VTune result dirs (large); only CSV reports are kept
New-Item -ItemType Directory -Force (Join-Path $here 'raw'), $work | Out-Null
$plain = 'INST_RETIRED.ANY,UOPS_RETIRED.SLOTS,UOPS_RETIRED.HEAVY,UOPS_RETIRED.MS,UOPS_RETIRED.ALL,UOPS_ISSUED.ANY,CPU_CLK_UNHALTED.THREAD,CPU_CLK_UNHALTED.CORE'
$prefixed = 'cpu_core/INST_RETIRED.ANY,cpu_core/UOPS_RETIRED.SLOTS,cpu_core/UOPS_RETIRED.HEAVY,cpu_core/UOPS_RETIRED.MS,cpu_core/CPU_CLK_UNHALTED.THREAD,cpu_atom/INST_RETIRED.ANY,cpu_atom/UOPS_RETIRED.ALL,cpu_atom/UOPS_RETIRED.MS,cpu_atom/UOPS_ISSUED.ANY,cpu_atom/CPU_CLK_UNHALTED.CORE'

function Measure-One($events, $cpu, $kernel, $tag, $log) {
    $r = Join-Path $work $tag
    if (Test-Path $r) { Remove-Item -Recurse -Force $r }
    $c = & $vt -collect-with runsa -knob counting-mode=true -knob event-mode=user -knob "event-config=$events" `
        -result-dir $r -- $exe $cpu $kernel 200000 25 2>&1
    $c | Out-File -Append -Encoding utf8 $log
    if ($LASTEXITCODE -ne 0) { return $false }
    $rep = & $vt -report summary -result-dir $r -format csv -csv-delimiter comma 2>&1
    $rep | Out-File -Encoding utf8 (Join-Path $here "raw\$tag.csv")
    $hw = & $vt -report hw-events -result-dir $r -group-by cpuid -format csv -csv-delimiter comma 2>&1
    $hw | Out-File -Encoding utf8 (Join-Path $here "raw\${tag}_hw.csv")
    return $true
}

# Probe: does hardware counting work, and which event spelling does this VTune accept?
$probe = Join-Path $here 'probe.log'
"probe $(Get-Date -Format s)  admin=$(([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrator'))" | Out-File -Encoding utf8 $probe
$events = $null
foreach ($cand in @($plain, $prefixed)) {
    "--- trying: $cand" | Out-File -Append -Encoding utf8 $probe
    if ((Measure-One $cand 12 'add_rr_chain' 'probe_E' $probe) -and (Measure-One $cand 2 'add_rr_chain' 'probe_P' $probe)) {
        $events = $cand; break
    }
}
if (-not $events) { "PROBE FAILED: hardware counting not available (see above)" | Out-File -Append -Encoding utf8 $probe; exit 1 }
"PROBE OK with: $events" | Out-File -Append -Encoding utf8 $probe
if ($ProbeOnly) { exit 0 }

# Full run: 4 CPUs x 5 kernels x 3 repeats
$log = Join-Path $here 'run.log'
"run $(Get-Date -Format s) events=$events" | Out-File -Encoding utf8 $log
foreach ($rep in 1..3) {
    foreach ($cpu in 12, 16, 2, 8) {
        foreach ($k in 'empty', 'add_rr_chain', 'e3B_nodisp', 'e3B_disp8', 'x2b_w_bi') {
            $ok = Measure-One $events $cpu $k "cpu${cpu}_${k}_r$rep" $log
            "$(Get-Date -Format s) cpu$cpu $k r$rep ok=$ok" | Out-File -Append -Encoding utf8 $log
        }
    }
}
"DONE $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $log
