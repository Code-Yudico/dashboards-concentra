# wsl-portproxy.ps1
#
# Reexpone hacia la red local los puertos de servicios que corren dentro de
# WSL2 (distro "dashboards"), ya que este equipo es Windows 10 y no soporta
# networkingMode=mirrored (requiere Windows 11 build 22621+) — ver
# docs/RUNBOOK.md, seccion "Exponer en la red de oficina".
#
# WSL2 en modo NAT clasico le asigna a la distro una IP interna que CAMBIA
# en cada reinicio de WSL (`wsl --shutdown` o reinicio de Windows). Por eso
# este script no es un ajuste de una sola vez: hay que volver a correrlo
# cada vez que cambia esa IP. Configuralo como Tarea Programada de Windows
# (Task Scheduler) con disparador "Al iniciar sesion" o "Al iniciar el
# equipo", ejecutandolo como Administrador.
#
# Ejecutar SIEMPRE como Administrador (netsh y New-NetFirewallRule lo
# requieren). Ejemplo manual:
#   powershell -ExecutionPolicy Bypass -File .\wsl-portproxy.ps1

$ErrorActionPreference = "Stop"

$distro = "dashboards"

# Puertos de servicios publicados por docker-compose en cada rama:
#   8081 -> dashboard-web (rama feature/dashboard-html-standalone)
#   3000 -> grafana (rama main)
$ports = @(8081, 3000)

$wslIpRaw = wsl -d $distro -- hostname -I
$wslIp = ($wslIpRaw -split "\s+")[0]

if ([string]::IsNullOrWhiteSpace($wslIp)) {
    Write-Error "No se pudo obtener la IP de WSL2 para la distro '$distro'. ¿Esta corriendo? (arrancala con 'wsl -d $distro' o abriendo un contenedor)."
    exit 1
}

Write-Output "IP interna de WSL2 ($distro): $wslIp"

foreach ($port in $ports) {
    # Limpia cualquier regla previa para este puerto (la IP de WSL2 pudo
    # haber cambiado desde la ultima vez que corrio este script).
    netsh interface portproxy delete v4tov4 listenport=$port listenaddress=0.0.0.0 | Out-Null

    netsh interface portproxy add v4tov4 `
        listenaddress=0.0.0.0 listenport=$port `
        connectaddress=$wslIp connectport=$port | Out-Null

    $ruleName = "WSL-$distro-$port"
    if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound `
            -LocalPort $port -Protocol TCP -Action Allow | Out-Null
        Write-Output "Regla de Firewall creada: $ruleName (puerto $port)"
    }
}

Write-Output ""
Write-Output "Reglas de portproxy activas:"
netsh interface portproxy show v4tov4
