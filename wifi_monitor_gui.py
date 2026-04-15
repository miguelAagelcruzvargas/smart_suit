# ============================================================
#  WIFI MONITOR GUI  — mqerkacademy 2026
#  Motor: wifi_monitor.py (reutilizado)
#  Interfaz: CustomTkinter (consistente en Win10 / Win11)
# ============================================================

import sys
import os
import ctypes
import time
import threading
import json
import re
import subprocess
import csv
import traceback
import socket
import urllib.request
from datetime import datetime
from collections import deque
import concurrent.futures

# ── Elevar privilegios antes de importar la GUI ──────────────
def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not _is_admin():
    try:
        # Usamos comillas para manejar rutas con espacios
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
    except Exception:
        pass
    sys.exit(0)

# ── Imports GUI ───────────────────────────────────────────────
try:
    import customtkinter as ctk
except ImportError:
    import subprocess as _sp
    _sp.run([sys.executable, "-m", "pip", "install", "customtkinter"], check=False)
    import customtkinter as ctk

from tkinter import messagebox
import tkinter as tk

# ══════════════════════════════════════════════════════════════
#  MOTOR DE DATOS  (idéntico al wifi_monitor.py original)
# ══════════════════════════════════════════════════════════════

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_LOG      = os.path.join(DIR_ACTUAL, "red_diag_log.csv")
ARCHIVO_ERRORES  = os.path.join(DIR_ACTUAL, "error_log.txt")
ARCHIVO_ALERTAS  = os.path.join(DIR_ACTUAL, "alertas_log.txt")
ARCHIVO_CONFIG   = os.path.join(DIR_ACTUAL, "config.json")
ARCHIVO_RESUMEN  = os.path.join(DIR_ACTUAL, "resumen_actual.json")

MAX_HISTORIAL = 60
TAMAÑO_BUFFER_LOGS = 10
HOST_TO_PING = "8.8.8.8"

DEFAULT_CONFIG = {
    "host_to_ping": "8.8.8.8",
    "intervalo_s": 1,
    "timeouts_ms": {"lan": 500, "wan": 1000},
    "frecuencias_s": {"wifi": 2, "gateway": 10, "drivers": 20, "conn": 20, "export": 60},
    "alertas": {
        "enabled": True,
        "beep": False,
        "cooldown_s": 20,
        "umbral_lat_lan_ms": 60,
        "umbral_lat_wan_ms": 150,
        "umbral_loss_pct": 10.0,
        "umbral_jitter_ms": 50
    },
    "export": {"enabled": True}
}

system_state = {
    "router_ip": None,
    "ultimo_codigo_estado": "INICIANDO",
    "caidas_wifi_timestamps": deque(maxlen=200),
    "caidas_internet_timestamps": deque(maxlen=200),
    "fallos_consecutivos_wifi": 0,
    "fallos_consecutivos_internet": 0,
    "driver_log_texto": "Escaneando registros de Windows en segundo plano...",
    "alerta_ultimo": None,
    "last_alert_ts": 0.0,
    "last_export_ts": 0.0,
    "last_speedtest_ts": 0.0,
    "is_paused": False,
    "speedtest_running": False,
    "speedtest_result": "",
    "prev_ok_local": True,
    "prev_ok_net": True,
}

data_cache = {
    "ssid": "Buscando...", "signal": 0, "speed": "0",
    "adapter_name": "Cargando...", "lat_local": 0.0, "lat_net": 0.0,
    "ok_local": False, "ok_net": False,
    "conn_type": "Detectando...", "adapter_model": "Detectando...",
    "conn_updated_at": None,
    "isp": "Buscando...",
    "wifi_channel": "?",
    "wifi_banda": "?",
}

historial_pings_local    = deque(maxlen=MAX_HISTORIAL)
historial_pings_internet = deque(maxlen=MAX_HISTORIAL)
log_buffer = []
pending_tasks = {}
CURRENT_CONFIG = {}

# ── Utilidades ─────────────────────────────────────────────────
def registrar_error_interno(msg):
    """
    Registra un mensaje de error interno en el archivo de errores.
    """
    try:
        with open(ARCHIVO_ERRORES, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {msg}\n")
    except:
        pass

def load_config():
    """
    Carga la configuración desde ARCHIVO_CONFIG, fusionando con DEFAULT_CONFIG.
    Devuelve un diccionario de configuración.
    """
    cfg = DEFAULT_CONFIG.copy()
    try:
        if os.path.exists(ARCHIVO_CONFIG):
            with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        else:
            with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        registrar_error_interno(f"Error config: {e}")
    return cfg

def registrar_alerta(msg):
    """
    Registra una alerta en el archivo de alertas.
    """
    try:
        with open(ARCHIVO_ALERTAS, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except:
        pass

def limpiar_texto(texto):
    """
    Limpia y decodifica texto, eliminando caracteres no válidos.
    """
    if not texto: return ""
    try:
        if isinstance(texto, bytes):
            return texto.decode("utf-8", "ignore")
        return texto.strip()
    except:
        return str(texto).encode("ascii", "ignore").decode("ascii")

def get_default_gateway():
    try:
        result = subprocess.run(
            ["route", "print", "-4"],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=3
        )
        match = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+([\d\.]+)\s+", result.stdout)
        if match:
            return match.group(1).strip()
    except Exception as e:
        registrar_error_interno(f"Error gateway: {e}")
    return None

def get_wifi_stats():
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=6
        )
        r = result.stdout
        signal_match = re.search(r"(?:Signal|Se.al|S.+al)\s*:\s*(\d+)%", r, re.IGNORECASE)
        # ⚠️ BUG FIX: Use negative look-behind to avoid matching "BSSID" line as SSID
        ssid_match   = re.search(r"(?<!B)SSID\s*:\s*(.+)", r, re.IGNORECASE)
        speed_match  = re.search(r"(?:Receive rate|Velocidad de recep|Velocidad de recepci.n).+\(Mbps\)\s*:\s*([\d.]+)", r, re.IGNORECASE)
        if not speed_match:
            speed_match = re.search(r"(?:recep|receiv).+\(Mbps\)\s*:\s*([\d.]+)", r, re.IGNORECASE)
        desc_match   = re.search(r"(?:Description|Descripci.n|Descripci.+n)\s*:\s*(.+)", r, re.IGNORECASE)
        if not desc_match:
            desc_match = re.search(r"(?:Descrip|Desc.+n)\s*:\s*(.+)", r, re.IGNORECASE)
        if not desc_match and ("no hay" in r.lower() or "is no" in r.lower()):
            return "NO HARDWARE", 0, "0", "USB DESCONECTADO / ADAPTADOR APAGADO"
        signal_pct = int(signal_match.group(1)) if signal_match else 0
        # Strip trailing whitespace/carriage-returns that latin-1 decoding can leave
        ssid_name  = ssid_match.group(1).strip() if ssid_match else "Desconectado"
        speed      = speed_match.group(1).strip() if speed_match else "0"
        adapter    = desc_match.group(1).strip() if desc_match else "Adaptador Desconocido"
        return limpiar_texto(ssid_name), signal_pct, speed, limpiar_texto(adapter)
    except Exception as e:
        registrar_error_interno(f"Error WiFi Stats: {e}")
        return "Error", 0, "0", "Fallo Lectura Adaptador"

def get_ethernet_stats():
    """Obtiene métricas del adaptador Ethernet activo: velocidad de enlace y nombre.
    Retorna (label, link_speed_mbps_str, adapter_desc) — misma forma que get_wifi_stats
    pero el primer campo indica que es Ethernet en lugar del SSID."""
    ps_cmd = (
        'Get-NetAdapter | Where-Object { $_.Status -eq "Up" -and $_.NdisPhysicalMedium -ne 9 } '
        '| Sort-Object LinkSpeed -Descending | Select-Object -First 1 '
        'Name, InterfaceDescription, LinkSpeed | ConvertTo-Json -Compress'
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=6
        )
        raw = result.stdout.strip()
        if raw and raw != "null":
            data = json.loads(raw)
            if isinstance(data, dict):
                desc  = limpiar_texto(str(data.get("InterfaceDescription") or data.get("Name") or "Ethernet")).strip()
                # LinkSpeed viene como "1 Gbps", "100 Mbps", etc.
                speed_raw = str(data.get("LinkSpeed") or "0")
                speed_match = re.search(r"([\d.]+)\s*(G|M)bps", speed_raw, re.IGNORECASE)
                if speed_match:
                    val  = float(speed_match.group(1))
                    unit = speed_match.group(2).upper()
                    speed_mbps = str(int(val * 1000)) if unit == "G" else str(int(val))
                else:
                    speed_mbps = "0"
                return "[Ethernet]", 100, speed_mbps, desc  # señal 100% = enlace físico
    except Exception as e:
        registrar_error_interno(f"Error Ethernet Stats: {e}")
    return "[Ethernet]", 100, "0", "Adaptador Ethernet"

def get_adaptive_link_stats():
    """Dispatch inteligente: devuelve stats WiFi o Ethernet según la conexión activa.
    Siempre retorna (ssid_o_label, signal_pct, speed_mbps, adapter_name)."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5
        )
        if re.search(r"(?:State|Estado)\s*:\s*(?:connected|conectado)", result.stdout, re.IGNORECASE):
            return get_wifi_stats()  # WiFi activo → métricas WiFi
    except Exception:
        pass
    return get_ethernet_stats()  # Fallback a Ethernet

def get_wifi_channel():
    """Retorna (canal, banda) del adaptador WiFi activo usando netsh."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=6
        )
        r = result.stdout
        channel_match = re.search(r"(?:Canal|Channel)\s*:\s*(\d+)", r, re.IGNORECASE)
        radio_match   = re.search(r"(?:Tipo de radio|Radio type)\s*:\s*(.+)", r, re.IGNORECASE)
        channel = channel_match.group(1).strip() if channel_match else "?"
        radio   = radio_match.group(1).strip() if radio_match else ""
        # Determinar banda por canal o radio type
        # ⚠️ BUG FIX: Añadir soporte Wi-Fi 6E (6 GHz, canales 1-233 reservados para 6GHz)
        try:
            ch_num = int(channel)
            if ch_num <= 14:
                banda = "2.4 GHz"
            elif ch_num <= 177:
                banda = "5 GHz"
            else:
                banda = "6 GHz"  # Wi-Fi 6E
        except ValueError:
            if "802.11a" in radio or "802.11ac" in radio:
                banda = "5 GHz"
            elif "802.11ax" in radio or "802.11be" in radio:
                # Wi-Fi 6E/7 puede operar en 6 GHz — sin canal numérico no podemos saber cuál
                banda = "5/6 GHz"
            elif radio:
                banda = "2.4 GHz"
            else:
                banda = "?"
        return channel, banda
    except Exception as e:
        registrar_error_interno(f"Error canal WiFi: {e}")
        return "?", "?"

def ping_host(host, timeout=1000):
    if not host or host == "Ninguna": return 0.0, False
    try:
        proc_timeout = (timeout / 1000.0) + 1.5
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout), host],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=proc_timeout
        )
        match = re.search(r"(?:tiempo|time)[=<]\s*([\d.,]+)\s*ms", result.stdout, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ".")), True
        return 0.0, False
    except:
        return 0.0, False

def ping_gateway_smart(host, timeout=500):
    """Ping inteligente al router/gateway local.
    1) Intenta ICMP normal.
    2) Si falla (router Telmex/ISP bloquea ICMP), prueba TCP en puertos
       comunes de administración web: 80, 443, 8080, 23 (telnet), 22 (ssh).
    3) Si TCP funciona → router VIVO pero bloquea ICMP → falso negativo.
       Marca system_state['router_icmp_blocked'] = True.
    Retorna (latencia_ms, ok_bool) con la misma firma que ping_host().
    """
    if not host:
        return 0.0, False

    # ─ Intento ICMP ─
    lat, ok = ping_host(host, timeout)
    if ok:
        system_state["router_icmp_blocked"] = False
        return lat, True

    # ─ Fallback TCP: puertos típicos de routers domésticos / Telmex ─
    t_sec = max(0.3, timeout / 1000.0)
    for port in [80, 443, 8080, 8443, 23, 22]:
        try:
            t0 = time.perf_counter()
            s  = socket.create_connection((host, port), timeout=t_sec)
            s.close()
            tcp_lat = (time.perf_counter() - t0) * 1000
            # Router responde por TCP → está vivo, solo ignora ICMP
            system_state["router_icmp_blocked"] = True
            return tcp_lat, True
        except OSError:
            continue

    # ─ Nada funcionó: realmente sin ruta al gateway ─
    system_state["router_icmp_blocked"] = False
    return 0.0, False

def get_driver_errors():
    ps_cmd = (
        'Get-WinEvent -LogName System -MaxEvents 5 -ErrorAction SilentlyContinue '
        '| Where-Object { $_.ProviderName -like "*WLAN*" -or $_.ProviderName -like "*Net*" } '
        '| ForEach-Object { "ID: $($_.Id) ($($_.ProviderName)) - $($_.Message)" }'
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10
        )
        res = result.stdout.strip()
        return limpiar_texto(res) if res else "Hardware WLAN OK. No se detectaron fallos a nivel SO."
    except subprocess.TimeoutExpired:
        return "Timeout leyendo Visor de Eventos."
    except Exception as e:
        return f"Error de PowerShell: {str(e)}"

def get_isp_info():
    """Retorna ISP, IP pública y ciudad en un solo string. Usa ip-api.com."""
    try:
        req = urllib.request.Request("http://ip-api.com/json", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            isp   = data.get("isp", "?")
            ip    = data.get("query", "?")
            city  = data.get("city", "?")
            region= data.get("regionName", "?")
            return f"{isp}  |  {ip}  ({city}, {region})"
    except Exception:
        return "Sin acceso a Internet o timeout"

def repair_network():
    """Ejecuta los 3 comandos de auto-reparación de red como administrador.
    Flush DNS + Reset Winsock + Renovar IP. Retorna el resultado del diagnóstico."""
    steps = [
        (["ipconfig", "/flushdns"],          "Flush DNS"),
        (["netsh", "winsock", "reset"],       "Reset Winsock"),
        (["netsh", "int", "ip", "reset"],     "Reset IP Stack"),
        (["ipconfig", "/release"],            "Release IP"),
        (["ipconfig", "/renew"],              "Renew IP (puede tardar...)"),
    ]
    results = []
    for cmd, label in steps:
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="latin-1", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=15
            )
            ok = r.returncode == 0
            results.append(f"{'✅' if ok else '⚠️'} {label}")
        except Exception as e:
            results.append(f"❌ {label}: {e}")
    return "\n".join(results)

def get_connection_info():
    ps_cmd = (
        'Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | '
        'Sort-Object { $_.NdisPhysicalMedium -eq 9 } -Descending | '  # Ndis 9 = Native802_11 (WiFi)
        'Select-Object -First 1 Name, InterfaceDescription, NdisPhysicalMedium, MediaType | '
        'ConvertTo-Json -Compress'
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=6
        )
        raw = result.stdout.strip()
        if raw and raw != "null":
            data = json.loads(raw)
            if isinstance(data, dict):
                name  = str(data.get("Name") or "").strip()
                desc  = str(data.get("InterfaceDescription") or "").strip()
                media = str(data.get("MediaType") or "").strip()
                ndis  = data.get("NdisPhysicalMedium")
                conn_type = "Desconocido"
                if "Wireless" in str(ndis) or "802.11" in media or ndis == 9:
                    conn_type = "WiFi"
                elif "802.3" in media or "Ethernet" in media or ndis == 14:
                    conn_type = "Ethernet"
                model = desc if desc else name
                return conn_type, limpiar_texto(model), name if name else model
    except Exception as e:
        registrar_error_interno(f"Error connection info: {e}")

    # Priorizar WiFi sobre Ethernet/Virtuales si PowerShell falla
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=6
        )
        r = result.stdout
        if re.search(r"(?:State|Estado)\s*:\s*(?:connected|conectado)", r, re.IGNORECASE):
            desc_match = re.search(r"(?:Description|Descripci.n)\s*:\s*(.+)", r, re.IGNORECASE)
            desc = desc_match.group(1).strip() if desc_match else "WiFi"
            return "WiFi", limpiar_texto(desc), desc
    except:
        pass
    return "Desconectado", "Sin adaptador activo", "Sin adaptador activo"

def calcular_jitter(historial):
    valid = [p for p in historial if p > 0]
    if len(valid) < 2: return 0.0
    return sum(abs(valid[i]-valid[i-1]) for i in range(1, len(valid))) / (len(valid)-1)

def scan_nearby_networks():
    """Escanea redes cercanas con un parser genérico de Clave: Valor."""
    try:
        # Ejecutar netsh con codificación para evitar errores de simbolos locales
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, text=True, encoding="latin-1", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=12
        )
        content = result.stdout
        networks = []
        current_ssid = "Red Oculta"
        
        for line in content.splitlines():
            line = line.strip()
            if not line or ":" not in line: continue
            
            # Dividir en Clave : Valor de forma genérica
            parts = line.split(":", 1)
            key = parts[0].strip().lower()
            val = parts[1].strip()
            
            # 1. Detectar Nueva Red (SSID)
            if key.startswith("ssid ") or key == "ssid":
                current_ssid = val or "Red Oculta"
                continue
                
            # 2. Detectar Nuevo Punto de Acceso (BSSID)
            if key.startswith("bssid ") or key == "bssid":
                networks.append({"ssid": current_ssid, "canal": None, "senal": 0, "banda": "?"})
                continue
            
            # 3. Si tenemos un punto de acceso en curso, capturar sus métricas
            if networks:
                last = networks[-1]
                # Buscar números en el valor de forma flexible
                nums = re.findall(r'\d+', val)
                
                # Caso: Canal
                if key.startswith("canal") or "channel" in key:
                    if nums: last["canal"] = int(nums[0])
                # Caso: Señal
                # ⚠️ BUG FIX: "se" era demasiado genérico y colisionaba con "seguridad", etc.
                # Usamos palabras clave más precisas.
                elif re.match(r"se.al|signal|se\xf1al", key, re.IGNORECASE):
                    if nums: last["senal"] = int(nums[0])
                # Caso: Banda
                elif "band" in key:
                    # Remplazar comas por puntos (ej: 2,4 -> 2.4)
                    last["banda"] = val.replace(",", ".").replace("GHz", "").strip()

        # Limpieza final: Quitar duplicados y entradas inválidas
        final_list = []
        for n in networks:
            if n["canal"] is not None and n["canal"] > 0:
                # Si la banda falló, deducirla por canal
                if n["banda"] == "?":
                    n["banda"] = "2.4" if n["canal"] <= 14 else "5"
                final_list.append(n)
        return final_list

    except Exception as e:
        registrar_error_interno(f"Error escáner avanzado: {e}")
        return []

def get_congestion_report(networks):
    """Analiza la saturación de canales y sugiere los mejores."""
    if not networks:
        return "No se detectaron redes cercanas para analizar.", []

    # Contar impacto por canal (peso por señal)
    impacto_24 = {i: 0 for i in [1, 6, 11]} # Canales estándar recomendados
    impacto_otros_24 = {}
    
    current_ch = None
    try:
        current_ch = int(data_cache.get("wifi_channel", 0))
    except: pass

    for net in networks:
        ch = net["canal"]
        sig = net["senal"]
        # Peso: señal fuerte (>70%) cuenta mnas
        peso = 1.5 if sig > 70 else (1.0 if sig > 40 else 0.5)
        
        if ch <= 14:
            # En 2.4GHz los canales se solapan. Un canal afecta a sus vecinos +/- 2
            # Pero simplificamos a los 3 pilares: 1, 6, 11
            for main_ch in [1, 6, 11]:
                if abs(ch - main_ch) <= 2:
                    impacto_24[main_ch] += peso
            if ch not in [1, 6, 11]:
                impacto_otros_24[ch] = impacto_otros_24.get(ch, 0) + peso
        
    # Construir reporte
    reporte = []
    reporte.append("📊 ANÁLISIS DE CONGESTIÓN (Banda 2.4 GHz)")
    reporte.append("──────────────────────────────────────")
    
    # Ordenar canales recomendados por menor impacto
    recomendados = sorted(impacto_24.items(), key=lambda x: x[1])
    
    for ch, imp in impacto_24.items():
        status = "🔴 Muy Saturado" if imp > 3 else ("🟡 Moderado" if imp > 1.5 else "🟢 Libre")
        prefix = "👉 TU CANAL" if ch == current_ch else "  "
        reporte.append(f"{prefix} Canal {ch:2}: {status} ({imp:.1f} pts)")

    best_ch = recomendados[0][0]
    if current_ch and current_ch == best_ch:
        reporte.append(f"\n✅ ¡Felicidades! Estás en el mejor canal posible ({best_ch}).")
    else:
        reporte.append(f"\n💡 RECOMENDACIÓN: Cambia al Canal {best_ch} para reducir interferencia.")
        
    return "\n".join(reporte), networks

def get_status_summary(ping_local_ok, ping_net_ok):
    ip              = system_state.get("router_ip")
    tcp_fallback    = system_state.get("tcp_fallback_active", False)
    icmp_bloqueado  = system_state.get("router_icmp_blocked", False)

    if not ip and not ping_local_ok:
        return "NO_IP", "RED LIMITADA: Esperando IP (¿DHCP atascado o Portal Cautivo?)", "#e74c3c"

    if ping_local_ok and ping_net_ok:
        if icmp_bloqueado:
            # Router vivo (TCP OK) pero bloquea ICMP — típico de Telmex, TP-Link, redes corporativas
            msg = "ESTABLE: Router bloquea Ping ICMP (normal en Telmex/ISP). Internet OK."
        elif tcp_fallback:
            msg = "OK CON RESTRICCIONES: Internet activo (ICMP externo bloqueado por Firewall/ISP)"
        else:
            msg = "EXCELENTE: Conexión e Internet Perfecta"
        return "OK", msg, "#00d26a"

    elif not ping_local_ok and ping_net_ok:
        # Router no responde NI por ICMP NI por TCP, pero sí hay internet (ruta alternativa)
        return "ROUTER_BLOCK", "ESTABLE: Internet OK. Router no responde (filtrado de paquetes activo)", "#3b9ef5"

    elif ping_local_ok and not ping_net_ok:
        return "NO_INTERNET", "MALO: Hay red local pero SIN INTERNET. (Navegación Imposible)", "#f5a623"

    else:
        return "NO_WIFI", "PÉSIMO: Sin ruta al gateway. Verifica cable/WiFi.", "#e74c3c"

def procesar_buffer_logs():
    global log_buffer
    if not log_buffer: return
    try:
        with open(ARCHIVO_LOG, mode="a", newline="", encoding="utf-8-sig") as fl:
            csv.writer(fl).writerows(log_buffer)
        log_buffer.clear()
    except Exception as e:
        registrar_error_interno(f"Fallo al escribir CSV: {e}")

def exportar_resumen():
    try:
        resumen = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ssid": data_cache.get("ssid"), "conn_type": data_cache.get("conn_type"),
            "adapter_model": data_cache.get("adapter_model"), "signal": data_cache.get("signal"),
            "speed_mbps": data_cache.get("speed"), "lat_local_ms": data_cache.get("lat_local"),
            "lat_net_ms": data_cache.get("lat_net"), "ok_local": data_cache.get("ok_local"),
            "ok_net": data_cache.get("ok_net"),
            "jitter_ms": round(calcular_jitter(historial_pings_internet), 2),
            # ⚠️ BUG FIX: snapshot de deque para evitar RuntimeError si se modifica en otro hilo
            "loss_wifi_pct": round((list(historial_pings_local).count(-1)/len(historial_pings_local))*100, 2) if historial_pings_local else 0.0,
            "loss_wan_pct": round((list(historial_pings_internet).count(-1)/len(historial_pings_internet))*100, 2) if historial_pings_internet else 0.0,
            "estado": system_state.get("ultimo_codigo_estado"),
        }
        with open(ARCHIVO_RESUMEN, "w", encoding="utf-8") as f:
            json.dump(resumen, f, ensure_ascii=False, indent=2)
    except Exception as e:
        registrar_error_interno(f"Error export resumen: {e}")

# ══════════════════════════════════════════════════════════════
#  PALETA & CONSTANTES DE DISEÑO
# ══════════════════════════════════════════════════════════════

DARK_BG      = "#0d1117"
PANEL_BG     = "#161b22"
PANEL_BORDER = "#30363d"
ACCENT       = "#1f6feb"
ACCENT_LITE  = "#388bfd"
TEXT_PRIMARY = "#e6edf3"
TEXT_DIM     = "#8b949e"
GREEN        = "#3fb950"
YELLOW       = "#d29922"
RED          = "#f85149"
CYAN         = "#39d353"
MAGENTA      = "#bc8cff"
ORANGE       = "#f0883e"

# Colores de señal
def signal_color(pct):
    if pct >= 75: return GREEN
    if pct >= 45: return YELLOW
    return RED

def lat_color(lat, ok, lim_ok, lim_warn):
    if not ok: return RED
    if lat < lim_ok: return GREEN
    if lat < lim_warn: return YELLOW
    return RED

# ══════════════════════════════════════════════════════════════
#  WIDGET PERSONALIZADO: TelemetryBar (canvas de historial)
# ══════════════════════════════════════════════════════════════

class TelemetryBar(tk.Canvas):
    """Canvas que dibuja la barra de telemetría tipo bar-chart en tiempo real."""
    BAR_W = 5
    GAP   = 1

    def __init__(self, parent, history_ref, **kwargs):
        kwargs.setdefault("bg", PANEL_BG)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(parent, **kwargs)
        self.history_ref = history_ref

    def refresh(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 2 or h < 2:
            return
        hist = list(self.history_ref)
        slot = self.BAR_W + self.GAP
        visible = max(1, w // slot)
        hist = hist[-visible:]

        max_val = max((p for p in hist if p > 0), default=200)
        max_val = max(max_val, 50)  # mínimo techo 50 ms para escala visible

        for i, val in enumerate(hist):
            x1 = i * slot
            x2 = x1 + self.BAR_W
            if val == -1:
                # caída → barra roja completa
                color = RED
                bar_h = h
            elif val == 0:
                color = TEXT_DIM
                bar_h = 3
            else:
                ratio = min(val / max_val, 1.0)
                bar_h = max(4, int(ratio * h))
                if val < 30:   color = GREEN
                elif val < 80: color = YELLOW
                elif val < 180: color = ORANGE
                else:          color = RED
            self.create_rectangle(x1, h - bar_h, x2, h, fill=color, outline="")

# ══════════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════

class WifiMonitorApp(ctk.CTk):
    REFRESH_MS = 250   # Refresh de la GUI (4× por segundo)

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("WiFi Diagnóstico — Network Intelligence")
        self.geometry("920x680")
        self.minsize(840, 600)
        self.configure(fg_color=DARK_BG)

        # ─ Ícono de la app (robusto: no crash si falta) ─
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass  # Sin ícono pero sin crash

        # ─ Centrar ventana en pantalla ─
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 920, 680
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Estado interno
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        self._ciclo    = 0
        self._tareas_p = {}
        self._running  = True
        self._cfg      = {}

        self._build_ui()
        self._init_csv()
        self._start_engine()
        self._schedule_refresh()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Construcción de la UI ─────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ─ HEADER ─────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0, height=48)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        hdr.grid_propagate(False)

        self._lbl_heartbeat = ctk.CTkLabel(
            hdr, text="●", font=("Segoe UI", 16, "bold"),
            text_color=TEXT_PRIMARY, width=30
        )
        self._lbl_heartbeat.grid(row=0, column=0, padx=(12, 4), pady=8)

        ctk.CTkLabel(
            hdr, text="NETWORK INTELLIGENCE  |",
            font=("Segoe UI", 14, "bold"), text_color=TEXT_PRIMARY
        ).grid(row=0, column=1, sticky="w", padx=4)

        self._lbl_adapter_hdr = ctk.CTkLabel(
            hdr, text="Cargando adaptador...",
            font=("Segoe UI", 12), text_color="#cce0ff"
        )
        self._lbl_adapter_hdr.grid(row=0, column=2, sticky="w", padx=8)

        self._lbl_clock = ctk.CTkLabel(
            hdr, text="00:00:00",
            font=("Segoe UI Mono", 14, "bold"), text_color=TEXT_PRIMARY
        )
        self._lbl_clock.grid(row=0, column=3, padx=16, pady=8)

        # ─ BODY ───────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color=DARK_BG, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 2))
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(2, weight=1)  # permite que telemetría crezca

        # ─ CONTADORES (4 tarjetas) ────────────────────────────
        cnt_frame = ctk.CTkFrame(body, fg_color=DARK_BG)
        cnt_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        cnt_frame.grid_columnconfigure((0,1,2,3), weight=1)

        self._card_wifi_drops  = self._make_card(cnt_frame, 0, "0", "Caídas WiFi (15 min)", RED)
        self._card_net_drops   = self._make_card(cnt_frame, 1, "0", "Caídas Internet (15 min)", YELLOW)
        self._card_loss_lan    = self._make_card(cnt_frame, 2, "0.0%", "Pérdida LAN", CYAN)
        self._card_loss_wan    = self._make_card(cnt_frame, 3, "0.0%", "Pérdida WAN", MAGENTA)

        # ─ STATS & VEREDICTO (fila 1) ─────────────────────────
        stats_frame = ctk.CTkFrame(body, fg_color=PANEL_BG, corner_radius=10, border_width=1, border_color=PANEL_BORDER)
        stats_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(0, 8))
        stats_frame.grid_columnconfigure(1, weight=1)

        self._stats_rows = {}
        fields = [
            ("ssid",    "🌐  Red (SSID)",        TEXT_PRIMARY),
            ("adapter", "📡  Adaptador",          MAGENTA),
            ("signal",  "📶  Señal / Velocidad",  GREEN),
            ("channel", "📻  Canal / Banda",       ACCENT_LITE),
            ("router",  "🏠  Latencia Router",    CYAN),
            ("internet","🌍  Latencia Google",    CYAN),
            ("jitter",  "📈  Jitter",             YELLOW),
            ("type",    "🔌  Tipo Conexión",      TEXT_DIM),
            ("isp",     "🏢  ISP / IP / Ciudad",  CYAN),
        ]
        ctk.CTkLabel(
            stats_frame, text="Telemetría en Vivo",
            font=("Segoe UI", 11, "bold"), text_color=ACCENT_LITE
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))

        for i, (key, label, color) in enumerate(fields, start=1):
            ctk.CTkLabel(
                stats_frame, text=label,
                font=("Segoe UI Emoji", 11), text_color=TEXT_DIM, anchor="w"
            ).grid(row=i, column=0, sticky="w", padx=12, pady=1)
            val_lbl = ctk.CTkLabel(
                stats_frame, text="—",
                font=("Segoe UI", 11, "bold"), text_color=color, anchor="e",
                justify="right", wraplength=220
            )
            val_lbl.grid(row=i, column=1, sticky="e", padx=12, pady=1)
            self._stats_rows[key] = val_lbl

        # ─ VEREDICTO ──────────────────────────────────────────
        verdict_outer = ctk.CTkFrame(body, fg_color=PANEL_BG, corner_radius=10, border_width=1, border_color=PANEL_BORDER)
        verdict_outer.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(0, 8))
        verdict_outer.grid_rowconfigure(1, weight=1)
        verdict_outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            verdict_outer, text="Veredicto",
            font=("Segoe UI", 11, "bold"), text_color=ACCENT_LITE
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self._verdict_box = ctk.CTkFrame(verdict_outer, fg_color=DARK_BG, corner_radius=8)
        self._verdict_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._verdict_box.grid_columnconfigure(0, weight=1)
        self._verdict_box.grid_rowconfigure(0, weight=1)

        self._lbl_status_icon = ctk.CTkLabel(
            self._verdict_box, text="⏳", font=("Segoe UI Emoji", 42)
        )
        self._lbl_status_icon.grid(row=0, column=0, pady=(6, 2))

        self._lbl_status_text = ctk.CTkLabel(
            self._verdict_box, text="Iniciando monitoreo…",
            font=("Segoe UI", 11, "bold"), text_color=TEXT_PRIMARY,
            wraplength=260, justify="center"
        )
        self._lbl_status_text.grid(row=1, column=0, padx=12, pady=(0, 4))

        self._lbl_alert = ctk.CTkLabel(
            self._verdict_box, text="",
            font=("Segoe UI", 9), text_color=YELLOW,
            wraplength=260, justify="center"
        )
        self._lbl_alert.grid(row=2, column=0, padx=12, pady=(0, 8))

        # ─ TELEMETRÍA GRÁFICA ─────────────────────────────────
        tele_frame = ctk.CTkFrame(body, fg_color=PANEL_BG, corner_radius=10, border_width=1, border_color=PANEL_BORDER)
        tele_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 5), pady=(0, 8))
        tele_frame.grid_columnconfigure(0, weight=1)
        tele_frame.grid_rowconfigure((1, 3), weight=1)

        ctk.CTkLabel(
            tele_frame, text="Telemetría Visual",
            font=("Segoe UI", 11, "bold"), text_color=ACCENT_LITE
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(6, 2))

        self._lbl_tele_wifi_state = ctk.CTkLabel(
            tele_frame, text="📡 Estabilidad WiFi  —",
            font=("Segoe UI", 9), text_color=CYAN, anchor="w"
        )
        self._lbl_tele_wifi_state.grid(row=1, column=0, sticky="w", padx=12)

        self._bar_wifi = TelemetryBar(tele_frame, historial_pings_local, height=36)
        self._bar_wifi.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 4))

        self._lbl_tele_net_state = ctk.CTkLabel(
            tele_frame, text="🌍 Estabilidad ISP   —",
            font=("Segoe UI", 9), text_color=MAGENTA, anchor="w"
        )
        self._lbl_tele_net_state.grid(row=3, column=0, sticky="w", padx=12)

        self._bar_net = TelemetryBar(tele_frame, historial_pings_internet, height=36)
        self._bar_net.grid(row=4, column=0, sticky="ew", padx=12, pady=(2, 6))

        # ─ DRIVER LOGS ────────────────────────────────────────
        drv_frame = ctk.CTkFrame(body, fg_color=PANEL_BG, corner_radius=10, border_width=1, border_color=PANEL_BORDER)
        drv_frame.grid(row=2, column=1, sticky="nsew", padx=(5, 0), pady=(0, 8))
        drv_frame.grid_columnconfigure(0, weight=1)
        drv_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            drv_frame, text="🔍 Logs de Drivers",
            font=("Segoe UI", 11, "bold"), text_color=ACCENT_LITE
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(6, 2))

        self._txt_drivers = ctk.CTkTextbox(
            drv_frame, fg_color=DARK_BG, text_color=TEXT_DIM,
            font=("Consolas", 9), corner_radius=6, wrap="word",
            border_width=0,
        )
        self._txt_drivers.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._txt_drivers.configure(state="disabled")

        # ─ FOOTER / CONTROLES ─────────────────────────────────
        foot = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0, height=42)
        foot.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        # Footer: 7 columnas (añadimos Reparar)
        foot.grid_columnconfigure((0,1,2,3,4,5,6,7), weight=1)
        foot.grid_propagate(False)

        self._btn_pause = ctk.CTkButton(
            foot, text="⏸ Pausar", width=95, height=28,
            fg_color="#21262d", hover_color=ACCENT, text_color=TEXT_PRIMARY,
            font=("Segoe UI Emoji", 11, "bold"), corner_radius=6, command=self._toggle_pause
        )
        self._btn_pause.grid(row=0, column=0, padx=2, pady=5)

        ctk.CTkButton(
            foot, text="⚡ Speed", width=95, height=28,
            fg_color="#21262d", hover_color="#5a3ea6", text_color=TEXT_PRIMARY,
            font=("Segoe UI Emoji", 11, "bold"), corner_radius=6, command=self._run_speedtest
        ).grid(row=0, column=1, padx=2, pady=5)

        ctk.CTkButton(
            foot, text="🛠️ Reparar", width=95, height=28,
            fg_color="#21262d", hover_color="#2c6e2c", text_color=TEXT_PRIMARY,
            font=("Segoe UI Emoji", 11, "bold"), corner_radius=6, command=self._run_repair
        ).grid(row=0, column=2, padx=2, pady=5)

        ctk.CTkButton(
            foot, text="📂 Logs", width=95, height=28,
            fg_color="#21262d", hover_color="#1a5c3a", text_color=TEXT_PRIMARY,
            font=("Segoe UI Emoji", 11, "bold"), corner_radius=6, command=lambda: os.startfile(DIR_ACTUAL)
        ).grid(row=0, column=3, padx=2, pady=5)

        ctk.CTkButton(
            foot, text="🔄 Reset", width=95, height=28,
            fg_color="#21262d", hover_color="#5a3010", text_color=TEXT_PRIMARY,
            font=("Segoe UI Emoji", 11, "bold"), corner_radius=6, command=self._reset_stats
        ).grid(row=0, column=4, padx=2, pady=5)

        ctk.CTkButton(
            foot, text="📡 Escáner", width=95, height=28,
            fg_color="#21262d", hover_color="#1f56b2", text_color=TEXT_PRIMARY,
            font=("Segoe UI Emoji", 11, "bold"), corner_radius=6, command=self._run_scan
        ).grid(row=0, column=5, padx=2, pady=5)

        ctk.CTkButton(
            foot, text="⚙️ Ajustes", width=95, height=28,
            fg_color="#21262d", hover_color="#8b949e", text_color=TEXT_PRIMARY,
            font=("Segoe UI Emoji", 11, "bold"), corner_radius=6, command=self._open_settings
        ).grid(row=0, column=6, padx=2, pady=5)

        ctk.CTkButton(
            foot, text="✖ Salir", width=95, height=28,
            fg_color="#21262d", hover_color="#6e1c1c", text_color=TEXT_PRIMARY,
            font=("Segoe UI Emoji", 11, "bold"), corner_radius=6, command=self._on_close
        ).grid(row=0, column=7, padx=2, pady=5)

    # ── Helpers UI ────────────────────────────────────────────

    def _make_card(self, parent, col, value, subtitle, color):
        card = ctk.CTkFrame(parent, fg_color=PANEL_BG, corner_radius=10, border_width=1, border_color=PANEL_BORDER)
        card.grid(row=0, column=col, sticky="ew", padx=4, pady=0)
        card.grid_columnconfigure(0, weight=1)
        val_lbl = ctk.CTkLabel(card, text=value, font=("Segoe UI", 22, "bold"), text_color=color)
        val_lbl.grid(row=0, column=0, pady=(10, 2))
        ctk.CTkLabel(card, text=subtitle, font=("Segoe UI", 9), text_color=TEXT_DIM).grid(row=1, column=0, pady=(0, 8))
        return val_lbl

    def _fmt_lat(self, lat, ok, lim_ok, lim_warn):
        if not ok: return "TIMEOUT", RED
        color = lat_color(lat, ok, lim_ok, lim_warn)
        return f"{lat:.1f} ms", color

    # ── Inicializar CSV ────────────────────────────────────────

    def _init_csv(self):
        os.makedirs(DIR_ACTUAL, exist_ok=True)
        if not os.path.exists(ARCHIVO_LOG):
            with open(ARCHIVO_LOG, mode="w", newline="", encoding="utf-8-sig") as fl:
                csv.writer(fl).writerow([
                    "Fecha", "SSID", "Senal_%", "Velocidad_Mbps",
                    "Latencia_Router", "Latencia_Internet", "Codigo_Estado", "Jitter_ms"
                ])

    # ── Botones ────────────────────────────────────────────────

    def _toggle_pause(self):
        system_state["is_paused"] = not system_state["is_paused"]
        if system_state["is_paused"]:
            self._btn_pause.configure(text="▶  Reanudar", fg_color=YELLOW, text_color=DARK_BG)
        else:
            self._btn_pause.configure(text="⏸  Pausar", fg_color="#21262d", text_color=TEXT_PRIMARY)

    def _run_speedtest(self):
        if system_state["speedtest_running"]:
            return
        self._executor.submit(self._handle_speedtest)

    def _handle_speedtest(self):
        system_state["speedtest_running"] = True
        try:
            res = subprocess.run(
                ["speedtest-cli", "--simple", "--secure"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=40
            )
            if res.returncode == 0:
                # El formato de salida es: Ping: x ms \n Download: x Mbit/s \n Upload: x Mbit/s
                out = res.stdout.strip()
                out = out.replace("Download:", "⬇️ DL:")
                out = out.replace("Upload:", "⬆️ UL:")
                out = out.replace("Mbit/s", "Mbps")
                # Eliminar los saltos de línea y formatear todo en una fila limpia
                formatted = out.replace("\n", "   |   ")
                system_state["speedtest_result"] = formatted
                system_state["last_speedtest_ts"] = time.time()
            else:
                system_state["speedtest_result"] = "Error al ejecutar Speedtest"
        except Exception as e:
            system_state["speedtest_result"] = f"Fallo: {str(e)}"
        finally:
            system_state["speedtest_running"] = False

    def _reset_stats(self):
        system_state["caidas_wifi_timestamps"].clear()
        system_state["caidas_internet_timestamps"].clear()
        historial_pings_local.clear()
        historial_pings_internet.clear()
        system_state["alerta_ultimo"] = None
        system_state["speedtest_result"] = ""

    def _run_repair(self):
        """Lanza la auto-reparación de red en un hilo separado y muestra resultado."""
        if system_state.get("repair_running"):
            return
        system_state["repair_running"] = True
        system_state["repair_result"] = "🔄 Ejecutando reparación de red... Por favor espera."
        self._executor.submit(self._handle_repair)

    def _handle_repair(self):
        result = repair_network()
        system_state["repair_result"] = result
        system_state["repair_running"] = False
        # Mostrar resultado en popup (desde el hilo de UI usando after)
        self.after(100, self._show_repair_result)

    def _show_repair_result(self):
        result = system_state.get("repair_result", "Sin resultados.")
        win = ctk.CTkToplevel(self)
        win.title("Resultado de Auto-Reparación")
        win.geometry("420x320")
        win.configure(fg_color=PANEL_BG)
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text="🛠️ Resultado de Reparación de Red",
                     font=("Segoe UI", 13, "bold"), text_color=GREEN).pack(pady=12)
        txt = ctk.CTkTextbox(win, fg_color=DARK_BG, text_color=TEXT_PRIMARY,
                              font=("Consolas", 10), corner_radius=6)
        txt.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        txt.insert("end", result)
        txt.configure(state="disabled")
        ctk.CTkLabel(win, text="⚠ Algunos cambios (Winsock/IP Stack) requieren reiniciar el equipo.",
                     font=("Segoe UI", 9), text_color=YELLOW, wraplength=380).pack(pady=4)
        ctk.CTkButton(win, text="Cerrar", command=win.destroy,
                      fg_color=PANEL_BORDER, hover_color="#1f2428", width=100).pack(pady=8)

    def _open_settings(self):
        if hasattr(self, "_settings_win") and self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.focus()
            return
            
        win = ctk.CTkToplevel(self)
        win.title("Ajustes Avanzados")
        win.geometry("450x420")
        win.configure(fg_color=PANEL_BG)
        win.transient(self) 
        self._settings_win = win
        
        ctk.CTkLabel(win, text="Parámetros Avanzados del Motor", font=("Segoe UI", 14, "bold"), text_color=ACCENT_LITE).pack(pady=15)
        
        frame = ctk.CTkFrame(win, fg_color=DARK_BG)
        frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        cfg = self._cfg
        
        def add_entry(parent, label, default_val):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=7, padx=10)
            ctk.CTkLabel(row, text=label, text_color=TEXT_PRIMARY, width=200, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=120, fg_color=PANEL_BG, border_color=PANEL_BORDER)
            entry.insert(0, str(default_val))
            entry.pack(side="right")
            return entry
            
        e_host = add_entry(frame, "IP/Dominio WAN a Pinguéar:", cfg.get("host_to_ping", "8.8.8.8"))
        e_inter = add_entry(frame, "Intervalo Refresco Motor (s):", cfg.get("intervalo_s", 1.0))
        e_t_lan = add_entry(frame, "Timeout crítico LAN (ms):", cfg.get("timeouts_ms", {}).get("lan", 500))
        e_t_wan = add_entry(frame, "Timeout crítico WAN (ms):", cfg.get("timeouts_ms", {}).get("wan", 1000))
        e_u_lan = add_entry(frame, "Alerta Latencia Alta LAN (ms):", cfg.get("alertas", {}).get("umbral_lat_lan_ms", 60))
        e_u_wan = add_entry(frame, "Alerta Latencia Alta WAN (ms):", cfg.get("alertas", {}).get("umbral_lat_wan_ms", 150))
        
        def save():
            """
            Valida y guarda los parámetros de configuración avanzada.
            """
            try:
                host = str(e_host.get().strip())
                if not host or len(host) < 3:
                    raise ValueError("El host no puede estar vacío.")
                intervalo = float(e_inter.get())
                if intervalo < 0.2:
                    raise ValueError("El intervalo debe ser mayor a 0.2 segundos.")
                t_lan = int(e_t_lan.get())
                t_wan = int(e_t_wan.get())
                if t_lan < 50 or t_wan < 50:
                    raise ValueError("Los timeouts deben ser mayores a 50 ms.")
                u_lan = float(e_u_lan.get())
                u_wan = float(e_u_wan.get())
                if u_lan < 10 or u_wan < 10:
                    raise ValueError("Los umbrales de latencia deben ser mayores a 10 ms.")

                cfg["host_to_ping"] = host
                cfg["intervalo_s"] = intervalo
                cfg.setdefault("timeouts_ms", {})["lan"] = t_lan
                cfg["timeouts_ms"]["wan"] = t_wan
                cfg.setdefault("alertas", {})["umbral_lat_lan_ms"] = u_lan
                cfg["alertas"]["umbral_lat_wan_ms"] = u_wan

                global HOST_TO_PING
                HOST_TO_PING = cfg["host_to_ping"]

                with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)

                win.destroy()
                messagebox.showinfo("Éxito", "Parámetros actualizados en el núcleo en tiempo real.")
            except ValueError as ve:
                messagebox.showerror("Error", f"Entrada inválida: {ve}")
            except Exception as e:
                messagebox.showerror("Error", f"Error inesperado: {e}")

        bf = ctk.CTkFrame(win, fg_color="transparent")
        bf.pack(fill="x", pady=15)
        ctk.CTkButton(bf, text="Guardar Cambios", command=save, fg_color=GREEN, hover_color="#2ea043").pack(side="left", expand=True, padx=20)
        ctk.CTkButton(bf, text="Cancelar", command=win.destroy, fg_color=PANEL_BORDER, hover_color="#1f2428").pack(side="right", expand=True, padx=20)

    def _run_scan(self):
        """Ejecuta el escáner de canales en segundo plano."""
        win = ctk.CTkToplevel(self)
        win.title("Escáner de Interferencia WiFi")
        win.geometry("500x550")
        win.configure(fg_color=PANEL_BG)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="📡 Escaneo de Canales Cercanos",
                     font=("Segoe UI", 14, "bold"), text_color=ACCENT_LITE).pack(pady=15)
        
        status_lbl = ctk.CTkLabel(win, text="🔍 Buscando redes y analizando interferencia...", font=("Segoe UI", 11))
        status_lbl.pack(pady=5)

        txt_frame = ctk.CTkFrame(win, fg_color=DARK_BG, corner_radius=8)
        txt_frame.pack(fill="both", expand=True, padx=15, pady=10)

        txt = ctk.CTkTextbox(txt_frame, fg_color="transparent", text_color=TEXT_PRIMARY,
                              font=("Consolas", 10), corner_radius=6)
        txt.pack(fill="both", expand=True, padx=5, pady=5)
        txt.insert("end", "Iniciando escaneo del espectro...\nEste proceso tarda unos segundos.")
        txt.configure(state="disabled")

        def _do_work():
            nets = scan_nearby_networks()
            report, _ = get_congestion_report(nets)
            
            self.after(0, lambda: _update_ui(nets, report))

        def _update_ui(nets, report):
            status_lbl.configure(text=f"✅ Escaneo completado. Se detectaron {len(nets)} redes cercanas.")
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("end", report)
            txt.insert("end", "\n\n📋 DETALLE DE REDES DETECTADAS:\n")
            txt.insert("end", "SSID".ljust(20) + " | Canal | Señal | Banda\n")
            txt.insert("end", "─" * 45 + "\n")
            
            # Ordenar por canal para que sea legible
            sorted_nets = sorted(nets, key=lambda x: x['canal'])
            for n in sorted_nets:
                ssid = (str(n['ssid'])[:18]).ljust(20)
                txt.insert("end", f"{ssid} | {str(n['canal']).center(5)} | {str(n['senal']).center(5)}% | {n['banda']} GHz\n")
            
            txt.configure(state="disabled")

        threading.Thread(target=_do_work, daemon=True).start()
        
        ctk.CTkButton(win, text="Entendido", command=win.destroy,
                      fg_color=ACCENT, hover_color=ACCENT_LITE, width=120).pack(pady=15)

    # ── Motor ─────────────────────────────────────────────────

    def _start_engine(self):
        global CURRENT_CONFIG, HOST_TO_PING
        self._cfg = load_config()
        CURRENT_CONFIG = self._cfg
        HOST_TO_PING = str(self._cfg.get("host_to_ping", HOST_TO_PING))
        system_state["router_ip"] = get_default_gateway()
        thr = threading.Thread(target=self._engine_loop, daemon=True)
        thr.start()


    def _intel_ping_with_backup(self, host, timeout, backup="1.1.1.1"):
        # Intento normal
        lat, ok = ping_host(host, timeout)
        if not ok:
            lat, ok = ping_host(backup, timeout)
            
        # [INTELIGENCIA ANTI-FALSOS POSITIVOS AVANZADA]
        # A veces el usuario tiene internet perfectamente, pero está en una red corporativa, VPN
        # o un hotel que "bloquea" los Pings (protocolo ICMP).
        # Si falló el ping al ISP de Google (8.8.8.8) y Cloudflare (1.1.1.1),
        # intentamos un SOCKET TCP rápido al puerto DNS (53) y HTTP (80).
        # ⚠️ BUG FIX: tcp_fallback_active se ponía False ANTES de retornar éxito.
        if not ok:
            t_sec = max(0.5, timeout / 1000.0)
            for _host, _port in [(backup, 53), (backup, 80), ("connectivitycheck.gstatic.com", 80)]:
                try:
                    t0 = time.perf_counter()
                    s = socket.create_connection((_host, _port), timeout=t_sec)
                    s.close()
                    tcp_lat = (time.perf_counter() - t0) * 1000
                    system_state["tcp_fallback_active"] = True
                    return tcp_lat, True  # Internet vivo pero ICMP bloqueado
                except OSError:
                    continue
        # Solo llega aquí si todos los intentos TCP fallaron O si el ping original sí funcionó
        system_state["tcp_fallback_active"] = False
        return lat, ok

    def _engine_loop(self):
        cfg = self._cfg
        tareas_p = self._tareas_p
        pending  = pending_tasks

        def submit_pending(key, func, *args):
            fut = pending.get(key)
            if fut is None or fut.done():
                pending[key] = self._executor.submit(func, *args)

        while self._running:
            try:
                if system_state["is_paused"]:
                    time.sleep(0.5)
                    continue

                self._ciclo += 1
                ciclo = self._ciclo

                # Recolectar resultados de pings previos
                if "ping_loc" in tareas_p and tareas_p["ping_loc"].done():
                    try:
                        lat, raw_ok = tareas_p["ping_loc"].result()
                        if raw_ok:
                            data_cache["lat_local"] = lat
                            system_state["fallos_consecutivos_wifi"] = 0
                            data_cache["ok_local"] = True
                        else:
                            system_state["fallos_consecutivos_wifi"] += 1
                            # ⚠️ BUG FIX: tolerancia de 1 ciclo causaba falsos negativos.
                            # Requerimos 3 fallos consecutivos antes de declarar la LAN caída.
                            data_cache["ok_local"] = system_state["fallos_consecutivos_wifi"] < 3
                    except: pass
                    del tareas_p["ping_loc"]

                if "ping_net" in tareas_p and tareas_p["ping_net"].done():
                    try:
                        lat, raw_ok = tareas_p["ping_net"].result()
                        if raw_ok:
                            data_cache["lat_net"] = lat
                            system_state["fallos_consecutivos_internet"] = 0
                            data_cache["ok_net"] = True
                        else:
                            system_state["fallos_consecutivos_internet"] += 1
                            # ⚠️ BUG FIX: misma tolerancia aplicada a WAN (3 fallos = caída real)
                            data_cache["ok_net"] = system_state["fallos_consecutivos_internet"] < 3
                    except: pass
                    del tareas_p["ping_net"]

                # Lanzar nuevos pings
                t_lan = int(cfg.get("timeouts_ms", {}).get("lan", 500))
                t_wan = int(cfg.get("timeouts_ms", {}).get("wan", 1000))
                ip = system_state["router_ip"]

                if "ping_loc" not in tareas_p:
                    if ip:
                        # ⚡ Usa ping_gateway_smart: ICMP + fallback TCP (routers Telmex que bloquean ICMP)
                        tareas_p["ping_loc"] = self._executor.submit(ping_gateway_smart, ip, t_lan)
                    else:
                        submit_pending("gw", get_default_gateway)
                        tareas_p["ping_loc"] = self._executor.submit(lambda: (0.0, False))

                if "ping_net" not in tareas_p:
                    tareas_p["ping_net"] = self._executor.submit(self._intel_ping_with_backup, HOST_TO_PING, t_wan)

                freqs = cfg.get("frecuencias_s", {})
                if ciclo % max(1, int(freqs.get("wifi", 2))) == 1:
                    # Dispatcher inteligente: elige WiFi o Ethernet automáticamente
                    submit_pending("wifi", get_adaptive_link_stats)
                if ciclo % max(1, int(freqs.get("gateway", 10))) == 1:
                    submit_pending("gw", get_default_gateway)
                if ciclo % 5 == 1:  # Canal WiFi cada ~5 ciclos
                    submit_pending("channel", get_wifi_channel)
                if ciclo % max(1, int(freqs.get("drivers", 20))) == 1:
                    submit_pending("driver", get_driver_errors)
                if ciclo % max(1, int(freqs.get("conn", 20))) == 1:
                    submit_pending("conn", get_connection_info)
                if cfg.get("export", {}).get("enabled", True) and ciclo % max(5, int(freqs.get("export", 60))) == 1:
                    submit_pending("export", exportar_resumen)

                if data_cache.get("ok_net") and data_cache.get("isp", "Buscando...") in ("Buscando...", "Sin acceso a Internet o timeout"):
                    if ciclo % 10 == 1:
                        submit_pending("isp", get_isp_info)

                # Actualizar caché desde resultados de background
                for key, dest in [
                    ("wifi", lambda r: data_cache.update(zip(
                        ["ssid", "signal", "speed", "adapter_name"], r
                    ))),
                    ("gw",   lambda r: system_state.update({"router_ip": r}) if r else None),
                    ("driver", lambda r: system_state.update({"driver_log_texto": r})),
                ]:
                    fut = pending.get(key)
                    if fut and fut.done():
                        try: dest(fut.result())
                        except: pass
                        pending.pop(key, None)

                fut = pending.get("conn")
                if fut and fut.done():
                    try:
                        ct, model, name = fut.result()
                        data_cache["conn_type"]    = ct
                        data_cache["adapter_model"]= model
                        if name: data_cache["adapter_name"] = name
                        data_cache["conn_updated_at"] = datetime.now().strftime("%H:%M:%S")
                    except: pass
                    pending.pop("conn", None)

                fut_isp = pending.get("isp")
                if fut_isp and fut_isp.done():
                    try: data_cache["isp"] = fut_isp.result()
                    except: pass
                    pending.pop("isp", None)

                fut_ch = pending.get("channel")
                if fut_ch and fut_ch.done():
                    try:
                        ch, banda = fut_ch.result()
                        data_cache["wifi_channel"] = ch
                        data_cache["wifi_banda"]   = banda
                    except: pass
                    pending.pop("channel", None)

                # Evaluar estado actual para decisiones inteligentes
                codigo_estado, _, _ = get_status_summary(data_cache["ok_local"], data_cache["ok_net"])
                router_bloquea_ping = (codigo_estado == "ROUTER_BLOCK")

                # Conteo de caídas
                # En ROUTER_BLOCK no contamos caída WiFi: el link físico SÍ existe,
                # solo el router ISP ignora el ping local (comportamiento normal en redes públicas).
                now_ts = time.time()
                if not data_cache["ok_local"] and not router_bloquea_ping and system_state.get("prev_ok_local", True):
                    system_state["caidas_wifi_timestamps"].append(now_ts)
                if not data_cache["ok_net"] and system_state.get("prev_ok_net", True):
                    system_state["caidas_internet_timestamps"].append(now_ts)
                system_state["prev_ok_local"] = data_cache["ok_local"]
                system_state["prev_ok_net"]   = data_cache["ok_net"]

                # Alertas
                alert_cfg = cfg.get("alertas", {})
                if alert_cfg.get("enabled", True):
                    cooldown  = float(alert_cfg.get("cooldown_s", 20))
                    jitter    = calcular_jitter(historial_pings_internet)
                    icmp_blk  = system_state.get("router_icmp_blocked", False)

                    # Loss LAN: ignorar si el router bloquea ICMP (serían falsos -1)
                    loss_lan_snap = list(historial_pings_local)
                    loss_wan_snap = list(historial_pings_internet)
                    loss_lan = (loss_lan_snap.count(-1) / len(loss_lan_snap) * 100) if (loss_lan_snap and not router_bloquea_ping and not icmp_blk) else 0
                    loss_wan = (loss_wan_snap.count(-1) / len(loss_wan_snap) * 100) if loss_wan_snap else 0

                    msg = None
                    # Solo alertar si el estado es realmente problemático
                    if codigo_estado in ("NO_WIFI", "NO_INTERNET", "NO_IP"):
                        msg = f"Estado crítico: {codigo_estado}"
                    elif codigo_estado == "OK":  # Solo alertas finas cuando la conexión está OK
                        if not icmp_blk and data_cache["ok_local"] and data_cache["lat_local"] > float(alert_cfg.get("umbral_lat_lan_ms", 60)):
                            msg = f"Latencia LAN alta: {data_cache['lat_local']:.1f} ms"
                        elif data_cache["ok_net"] and data_cache["lat_net"] > float(alert_cfg.get("umbral_lat_wan_ms", 150)):
                            msg = f"Latencia WAN alta: {data_cache['lat_net']:.1f} ms"
                        elif loss_lan > float(alert_cfg.get("umbral_loss_pct", 10)):
                            msg = f"Pérdida LAN alta: {loss_lan:.1f}%"
                        elif loss_wan > float(alert_cfg.get("umbral_loss_pct", 10)):
                            msg = f"Pérdida WAN alta: {loss_wan:.1f}%"
                        elif jitter > float(alert_cfg.get("umbral_jitter_ms", 50)):
                            msg = f"Jitter alto: {jitter:.1f} ms"

                    if msg and (now_ts - system_state["last_alert_ts"] >= cooldown or msg != system_state.get("alerta_ultimo")):
                        system_state["alerta_ultimo"] = msg
                        system_state["last_alert_ts"] = now_ts
                        registrar_alerta(msg)
                    elif not msg:
                        # Si no hay alerta activa, limpiar la última para no mostrar info vieja
                        if now_ts - system_state.get("last_alert_ts", 0) > 120:
                            system_state["alerta_ultimo"] = None

                # ── HISTORIAL INTELIGENTE ───────────────────────────────────────────
                # ROUTER_BLOCK: el WiFi físicamente funciona, los paquetes WAN viajan
                # por él. Usamos la latencia WAN como indicador de calidad del enlace
                # WiFi en lugar de -1 (falso negativo / caída falsa).
                if router_bloquea_ping:
                    # Proxy: la calidad WiFi se refleja en cuánto tarda en llegar a Google
                    proxy_wifi = data_cache["lat_net"] if data_cache["ok_net"] else -1
                    historial_pings_local.append(proxy_wifi)
                else:
                    historial_pings_local.append(data_cache["lat_local"] if data_cache["ok_local"] else -1)
                historial_pings_internet.append(data_cache["lat_net"] if data_cache["ok_net"] else -1)
                system_state["router_block_activo"] = router_bloquea_ping

                # CSV buffer
                codigo_estado, _, _ = get_status_summary(data_cache["ok_local"], data_cache["ok_net"])
                system_state["ultimo_codigo_estado"] = codigo_estado
                log_buffer.append([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    data_cache["ssid"], data_cache["signal"], data_cache["speed"],
                    data_cache["lat_local"] if data_cache["ok_local"] else "TIMEOUT",
                    data_cache["lat_net"] if data_cache["ok_net"] else "TIMEOUT",
                    codigo_estado,
                    round(calcular_jitter(historial_pings_internet), 2)
                ])
                if len(log_buffer) >= TAMAÑO_BUFFER_LOGS:
                    procesar_buffer_logs()

                time.sleep(float(self._cfg.get("intervalo_s", 1)))

            except Exception as e:
                registrar_error_interno(f"Error en engine loop: {e}\n{traceback.format_exc()}")
                time.sleep(1)

    # ── Actualización de UI (hilo principal, 4×/s) ────────────

    def _schedule_refresh(self):
        if self._running:
            self._refresh_ui()
            self.after(self.REFRESH_MS, self._schedule_refresh)

    def _refresh_ui(self):
        c = data_cache
        now_ts = time.time()

        # ─ Reloj y latido ─
        self._lbl_clock.configure(text=datetime.now().strftime("%H:%M:%S"))
        beat = "●" if int(time.time()) % 2 == 0 else "○"
        self._lbl_heartbeat.configure(text=beat, text_color=GREEN if c["ok_net"] else RED)

        # ─ Adaptador en header ─
        model = c.get("adapter_model") or c.get("adapter_name", "")
        self._lbl_adapter_hdr.configure(text=model[:50] if model else "—")

        # ─ Contadores ─
        recent_wifi = len([ts for ts in system_state["caidas_wifi_timestamps"] if now_ts - ts < 900])
        recent_net  = len([ts for ts in system_state["caidas_internet_timestamps"] if now_ts - ts < 900])
        loss_lan = (historial_pings_local.count(-1)/len(historial_pings_local)*100) if historial_pings_local else 0.0
        loss_wan = (historial_pings_internet.count(-1)/len(historial_pings_internet)*100) if historial_pings_internet else 0.0

        self._card_wifi_drops.configure(text=str(recent_wifi), text_color=RED if recent_wifi > 0 else TEXT_DIM)
        self._card_net_drops.configure(text=str(recent_net),  text_color=YELLOW if recent_net > 0 else TEXT_DIM)
        self._card_loss_lan.configure(text=f"{loss_lan:.1f}%", text_color=RED if loss_lan > 5 else CYAN)
        self._card_loss_wan.configure(text=f"{loss_wan:.1f}%", text_color=RED if loss_wan > 5 else MAGENTA)

        # ─ Stats — adaptados a WiFi o Ethernet ─
        is_ethernet = c.get("conn_type", "") == "Ethernet" or str(c.get("ssid", "")).startswith("[Ethernet]")

        if is_ethernet:
            # Ethernet: SSID no aplica, señal = calidad del enlace físico (100% si UP)
            self._stats_rows["ssid"].configure(
                text="Ethernet (cable)", text_color=CYAN
            )
            self._stats_rows["signal"].configure(
                text=f"Enlace físico  /  {c['speed']} Mbps", text_color=GREEN
            )
            self._stats_rows["channel"].configure(
                text="N/A (conexión por cable)", text_color=TEXT_DIM
            )
        else:
            s_color = signal_color(c["signal"])
            self._stats_rows["ssid"].configure(
                text=str(c["ssid"])[:30] or "—", text_color=TEXT_PRIMARY
            )
            self._stats_rows["signal"].configure(
                text=f"{c['signal']}%  /  {c['speed']} Mbps", text_color=s_color
            )
            ch   = c.get("wifi_channel", "?")
            band = c.get("wifi_banda", "?")
            band_color = YELLOW if band == "2.4 GHz" else ACCENT_LITE
            self._stats_rows["channel"].configure(text=f"Canal {ch}  /  {band}", text_color=band_color)

        self._stats_rows["adapter"].configure(text=(c.get("adapter_model") or c.get("adapter_name", "—"))[:35])
        router_txt, router_col  = self._fmt_lat(c["lat_local"], c["ok_local"], 20, 60)
        internet_txt, net_col   = self._fmt_lat(c["lat_net"], c["ok_net"], 70, 150)
        jitter_val = calcular_jitter(historial_pings_internet)

        self._stats_rows["router"].configure(text=router_txt, text_color=router_col)
        self._stats_rows["internet"].configure(text=internet_txt, text_color=net_col)
        self._stats_rows["jitter"].configure(text=f"{jitter_val:.1f} ms", text_color=YELLOW if jitter_val > 30 else CYAN)
        self._stats_rows["type"].configure(text=c.get("conn_type", "—"))
        self._stats_rows["isp"].configure(text=str(c.get("isp", "—"))[:60])

        # ─ Veredicto ─
        codigo, msg, color = get_status_summary(c["ok_local"], c["ok_net"])
        icon_map = {"OK": "✔️", "ROUTER_BLOCK": "ℹ️", "NO_INTERNET": "⚠️", "NO_WIFI": "❌"}

        if system_state["is_paused"]:
            icon, msg, color = "⏸", "MONITOREO PAUSADO", YELLOW
        elif system_state["speedtest_running"]:
            icon, msg, color = "⚡", "Realizando Speedtest…", MAGENTA
        else:
            icon = icon_map.get(codigo, "⏳")
            if system_state.get("speedtest_result") and (now_ts - system_state.get("last_speedtest_ts", 0) < 900):
                msg += f"\n\n📊 {system_state['speedtest_result']}"

        self._lbl_status_icon.configure(text=icon)
        self._lbl_status_text.configure(text=msg, text_color=color)

        alerta = system_state.get("alerta_ultimo")
        if alerta and (now_ts - system_state.get("last_alert_ts", 0) < 900):
            self._lbl_alert.configure(text=f"⚠ {alerta}")
        else:
            self._lbl_alert.configure(text="")

        # ─ Telemetría visual ─
        router_block = system_state.get("router_block_activo", False)

        def trend_label_wifi(hist):
            """Etiqueta para la estabilidad WiFi. Si el router ISP bloquea pings,
            se indica 'ACTIVO' en lugar de 'CAÍDO' para no confundir al usuario."""
            if not hist: return "Calculando…"
            last = list(hist)[-1] if hist else -1
            if last == -1:
                # Solo mostrar CAÍDO si NO es ROUTER_BLOCK — si lo es, el WiFi sí funciona
                return "ACTIVO (Router Oculto) 🔵" if router_block else "CAÍDO 🔴"
            if last < 30:  return "EXCELENTE 🟢"
            if last < 100: return "ESTABLE 🟡"
            if last < 300: return "INESTABLE 🟠"
            return "SATURADO 🔴"

        def trend_label_isp(hist):
            if not hist: return "Calculando…"
            last = list(hist)[-1] if hist else -1
            if last == -1: return "CAÍDO 🔴"
            if last < 50:  return "EXCELENTE 🟢"
            if last < 150: return "ESTABLE 🟡"
            if last < 400: return "INESTABLE 🟠"
            return "SATURADO 🔴"

        self._lbl_tele_wifi_state.configure(
            text=f"📡 Estabilidad WiFi  —  {trend_label_wifi(historial_pings_local)}"
        )
        self._lbl_tele_net_state.configure(
            text=f"🌍 Estabilidad ISP   —  {trend_label_isp(historial_pings_internet)}"
        )
        self._bar_wifi.refresh()
        self._bar_net.refresh()

        # ─ Drivers ─
        drv_txt = system_state.get("driver_log_texto", "")
        self._txt_drivers.configure(state="normal")
        self._txt_drivers.delete("1.0", "end")
        self._txt_drivers.insert("end", drv_txt[:800] if drv_txt else "Sin datos aún…")
        self._txt_drivers.configure(state="disabled")

    # ── Cierre limpio ─────────────────────────────────────────

    def _on_close(self):
        self._running = False
        procesar_buffer_logs()
        self._executor.shutdown(wait=False)
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    def _handle_uncaught(exc_type, exc_value, exc_tb):
        """Captura cualquier error no manejado y lo registra antes de morir."""
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        registrar_error_interno(f"ERROR CRITICO NO MANEJADO:\n{msg}")
        try:
            from tkinter import messagebox
            messagebox.showerror("Error inesperado",
                f"El programa encontró un error.\nRevisa 'error_log.txt' para detalles.\n\n{exc_value}")
        except Exception:
            pass

    sys.excepthook = _handle_uncaught

    try:
        app = WifiMonitorApp()
        app.mainloop()
    except Exception as e:
        registrar_error_interno(f"Error al iniciar la app: {e}\n{traceback.format_exc()}")
