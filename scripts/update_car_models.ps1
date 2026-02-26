# update_car_models.ps1
# Fetches vehicle data from the LMU REST API and updates Backend/car_models.json
# with new signatures while preserving existing car model names.

$ErrorActionPreference = 'Stop'

$scriptDir = $PSScriptRoot
$carModelsPath = Join-Path $scriptDir '..\Backend\car_models.json'
$apiUrl = 'http://localhost:6397/rest/sessions/getAllVehicles'

# --- 1. Fetch vehicle data from API ---

Write-Host "Fetching vehicle data from $apiUrl ..."
try {
    $vehicles = Invoke-RestMethod -Uri $apiUrl -Method Get
} catch {
    Write-Host "ERROR: Failed to fetch data from $apiUrl" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}
Write-Host "  Fetched $($vehicles.Count) vehicle entries"

# --- 2. Read existing car_models.json ---

if (-not (Test-Path $carModelsPath)) {
    Write-Host "ERROR: car_models.json not found at $carModelsPath" -ForegroundColor Red
    exit 1
}

$carModels = Get-Content -Path $carModelsPath -Raw | ConvertFrom-Json

# Build reverse map: car name -> old sig
$existingNames = @{}  # carName -> oldSig
foreach ($prop in $carModels.PSObject.Properties) {
    $existingNames[$prop.Value] = $prop.Name
}
Write-Host "  Existing car models: $($existingNames.Count)"

# --- 3. Build signature -> car info mapping ---

# Each unique signature represents a distinct physical car model.
# We take one representative entry per sig.
$sigInfo = @{}  # sig -> @{ Name; Classes; VehFile }

foreach ($v in $vehicles) {
    if (-not $v.sig -or $sigInfo.ContainsKey($v.sig)) { continue }

    $parts = $v.fullPathTree -split ','
    $name  = $parts[-1].Trim()

    $sigInfo[$v.sig] = @{
        Name    = $name
        Classes = $v.classes
        VehFile = $v.vehFile
    }
}
Write-Host "  Unique signatures found: $($sigInfo.Count)"

# Build API name -> list of sigs (a name like "Oreca 07" may have multiple sigs)
$nameToSigs = @{}
foreach ($sig in $sigInfo.Keys) {
    $name = $sigInfo[$sig].Name
    if (-not $nameToSigs.ContainsKey($name)) {
        $nameToSigs[$name] = @()
    }
    $nameToSigs[$name] += $sig
}

# --- 4. Word-overlap scoring for fuzzy matching ---

function Get-WordOverlapScore {
    param([string]$A, [string]$B)
    $wordsA = @($A -split '\s+' | ForEach-Object { $_.ToLower() })
    $wordsB = @($B -split '\s+' | ForEach-Object { $_.ToLower() })
    $shared = @($wordsA | Where-Object { $_ -in $wordsB }).Count
    $maxLen = [Math]::Max($wordsA.Count, $wordsB.Count)
    if ($maxLen -eq 0) { return 0 }
    return $shared / $maxLen
}

# --- 5. Match each existing car name to new signature(s) ---

$newMap      = [ordered]@{}  # sig -> carName  (the final output)
$matchedSigs = @{}           # sigs that have been claimed

Write-Host ""
Write-Host "Matching car models..."

foreach ($carName in @($existingNames.Keys)) {
    $matched = $false

    # -- 5a. Exact match ---
    if ($nameToSigs.ContainsKey($carName)) {
        foreach ($sig in $nameToSigs[$carName]) {
            $newMap[$sig]      = $carName
            $matchedSigs[$sig] = $true
        }
        $matched = $true
    }

    # -- 5b. Special-case disambiguation --
    #   Handles car models where the API name is ambiguous (same fullPathTree
    #   name maps to multiple distinct physical variants).
    if (-not $matched) {

        # Oreca 07 WEC vs ELMS — differentiated by class
        if ($carName -eq 'Oreca 07 WEC' -and $nameToSigs.ContainsKey('Oreca 07')) {
            foreach ($sig in $nameToSigs['Oreca 07']) {
                if ($sigInfo[$sig].Classes -notcontains 'LMP2_ELMS') {
                    $newMap[$sig]      = $carName
                    $matchedSigs[$sig] = $true
                    $matched = $true
                }
            }
        }
        elseif ($carName -eq 'Oreca 07 ELMS' -and $nameToSigs.ContainsKey('Oreca 07')) {
            foreach ($sig in $nameToSigs['Oreca 07']) {
                if ($sigInfo[$sig].Classes -contains 'LMP2_ELMS') {
                    $newMap[$sig]      = $carName
                    $matchedSigs[$sig] = $true
                    $matched = $true
                }
            }
        }

        # Peugeot 9x8 (Wingless) vs (Winged) — differentiated by vehFile path
        elseif ($carName -eq 'Peugeot 9x8 (Wingless)' -and $nameToSigs.ContainsKey('Peugeot 9x8')) {
            foreach ($sig in $nameToSigs['Peugeot 9x8']) {
                if ($sigInfo[$sig].VehFile -match 'Peugeot_9x8_2023') {
                    $newMap[$sig]      = $carName
                    $matchedSigs[$sig] = $true
                    $matched = $true
                }
            }
        }
        elseif ($carName -eq 'Peugeot 9x8 (Winged)' -and $nameToSigs.ContainsKey('Peugeot 9x8')) {
            foreach ($sig in $nameToSigs['Peugeot 9x8']) {
                if ($sigInfo[$sig].VehFile -notmatch 'Peugeot_9x8_2023') {
                    $newMap[$sig]      = $carName
                    $matchedSigs[$sig] = $true
                    $matched = $true
                }
            }
        }
    }

    # -- 5c. Fuzzy match by word overlap ---
    #   Handles cases where API names differ slightly from car_models names:
    #     API: "Aston Martin Vantage AMR"       -> car_models: "Aston Martin Vantage GTE"
    #     API: "Porsche 911 GT3 R LMGT3"        -> car_models: "Porsche 911 GT3 R"
    #     API: "Lamborghini Huracan LMGT3 Evo2" -> car_models: "Lamborghini Huracan Evo2"
    #     etc.
    if (-not $matched) {
        $bestScore = 0
        $bestName  = $null

        foreach ($apiName in $nameToSigs.Keys) {
            # Only consider names that still have at least one unmatched sig
            $hasUnmatched = $false
            foreach ($sig in $nameToSigs[$apiName]) {
                if (-not $matchedSigs.ContainsKey($sig)) {
                    $hasUnmatched = $true
                    break
                }
            }
            if (-not $hasUnmatched) { continue }

            $score = Get-WordOverlapScore -A $carName -B $apiName
            if ($score -gt $bestScore) {
                $bestScore = $score
                $bestName  = $apiName
            }
        }

        if ($bestName -and $bestScore -ge 0.5) {
            foreach ($sig in $nameToSigs[$bestName]) {
                if (-not $matchedSigs.ContainsKey($sig)) {
                    $newMap[$sig]      = $carName
                    $matchedSigs[$sig] = $true
                    $matched = $true
                }
            }
            Write-Host "  Fuzzy: '$carName' -> '$bestName' (score $([math]::Round($bestScore, 2)))" -ForegroundColor Yellow
        }
    }

    # -- 5d. No match - keep old signature ---
    if (-not $matched) {
        $oldSig = $existingNames[$carName]
        $newMap[$oldSig] = $carName
        Write-Host "  No match for '$carName' - keeping old signature" -ForegroundColor Red
    }
}

# --- 6. Add any new car models not already in car_models.json ---

$newCars = @()
foreach ($sig in $sigInfo.Keys) {
    if (-not $matchedSigs.ContainsKey($sig)) {
        $name = $sigInfo[$sig].Name
        $newMap[$sig] = $name
        $newCars += $name
    }
}

if ($newCars.Count -gt 0) {
    Write-Host ""
    Write-Host "New car models added:" -ForegroundColor Cyan
    foreach ($name in ($newCars | Sort-Object -Unique)) {
        Write-Host "  + $name" -ForegroundColor Cyan
    }
}

# --- 7. Write updated car_models.json ---

# Sort entries alphabetically by car name for consistency
$sorted = [ordered]@{}
foreach ($key in ($newMap.Keys | Sort-Object { $newMap[$_] })) {
    $sorted[$key] = $newMap[$key]
}

$json = $sorted | ConvertTo-Json -Depth 1

# Write UTF-8 without BOM to match typical JSON files
[System.IO.File]::WriteAllText(
    $carModelsPath,
    $json,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "Updated $carModelsPath" -ForegroundColor Green
Write-Host "  Total entries: $($sorted.Count)"
