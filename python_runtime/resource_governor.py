"""
Panther Agent - Resource Governor
Continuous hardware metric monitoring, pressure detection, and execution gating.
Tailored for low-resource 6 GB RAM & low-end dual-core CPU machines.
"""

import os
import sys
import time
import platform
import ctypes
import logging
from typing import Dict, Any, Tuple, Optional
from database import DatabaseManager
from config_manager import ConfigManager

logger = logging.getLogger("panther.resource_governor")

class ResourcePressure:
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"    # Advise smaller context, longer throttling delays
    HIGH = "HIGH"            # Pause non-critical observations, throttle model calls
    CRITICAL = "CRITICAL"    # Pause execution, reject new turns until recovery

class ResourceGovernor:
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        self.db = db
        self.config = config
        self.is_windows = platform.system().lower() == "windows"
        self._last_cpu_times: Optional[Tuple[float, float]] = None
        self._last_sample_time: float = 0
        self._cached_metrics: Optional[Dict[str, Any]] = None

    def sample_metrics(self, force: bool = False) -> Dict[str, Any]:
        """Samples RAM, process footprint, CPU usage, and determines pressure."""
        now = time.time()
        if not force and self._cached_metrics and (now - self._last_sample_time < 0.8):
            return self._cached_metrics

        total_ram_mb, avail_ram_mb = self._get_system_memory()
        process_mem_mb = self._get_process_memory()
        cpu_percent = self._get_cpu_percent()
        
        # Estimate model memory from active configuration
        model_name = self.config.get_value("model", "selected_model", "llama3.2:1b")
        model_mem_mb = self._estimate_model_memory(model_name)
        total_panther_mb = process_mem_mb + model_mem_mb

        res_limits = self.config.get_section("resource_limits")
        min_avail = res_limits.get("min_available_ram_mb", 1024)
        crit_avail = res_limits.get("critical_available_ram_mb", 512)
        max_agent = res_limits.get("max_agent_ram_mb", 450)
        max_cpu = res_limits.get("max_cpu_percent_sustained", 85.0)

        # Determine pressure state
        pressure = ResourcePressure.NORMAL
        reason = "Resources within nominal operational thresholds."

        if avail_ram_mb <= crit_avail:
            pressure = ResourcePressure.CRITICAL
            reason = f"Critical RAM starvation: available RAM ({avail_ram_mb} MB) <= threshold ({crit_avail} MB)."
        elif avail_ram_mb <= min_avail:
            pressure = ResourcePressure.HIGH
            reason = f"Low available RAM: available RAM ({avail_ram_mb} MB) <= warning threshold ({min_avail} MB)."
        elif cpu_percent > max_cpu:
            pressure = ResourcePressure.HIGH
            reason = f"High sustained CPU load: {cpu_percent:.1f}% > {max_cpu}%."
        elif process_mem_mb > max_agent:
            pressure = ResourcePressure.MODERATE
            reason = f"Agent process footprint ({process_mem_mb} MB) exceeds soft limit ({max_agent} MB)."

        metrics = {
            "total_ram_mb": total_ram_mb,
            "available_ram_mb": avail_ram_mb,
            "used_ram_mb": max(0, total_ram_mb - avail_ram_mb),
            "ram_used_percent": round((1.0 - (avail_ram_mb / max(1, total_ram_mb))) * 100, 1),
            "process_memory_mb": process_mem_mb,
            "model_process_memory_mb": model_mem_mb,
            "application_memory_mb": total_panther_mb,
            "cpu_percent": round(cpu_percent, 1),
            "system_pressure": pressure,
            "pressure_reason": reason,
            "timestamp": now,
            "platform": platform.system(),
        }

        self._cached_metrics = metrics
        self._last_sample_time = now

        if pressure in (ResourcePressure.HIGH, ResourcePressure.CRITICAL):
            self.db.log_diagnostic(
                "WARNING" if pressure == ResourcePressure.HIGH else "ERROR",
                "ResourceGovernor",
                reason,
                {"metrics": metrics}
            )

        return metrics

    def can_proceed_safely(self) -> Tuple[bool, str]:
        """Gating check before performing an observe/reason/act turn."""
        metrics = self.sample_metrics(force=True)
        pressure = metrics["system_pressure"]
        if pressure == ResourcePressure.CRITICAL:
            return False, f"Halted by Resource Governor: {metrics['pressure_reason']}"
        return True, "Safe"

    def should_throttle(self) -> bool:
        """Indicates whether execution should inject extra throttling delay."""
        metrics = self.sample_metrics()
        return metrics["system_pressure"] in (ResourcePressure.MODERATE, ResourcePressure.HIGH)

    def get_recommended_delays(self) -> Dict[str, int]:
        """Returns throttle delays based on current pressure."""
        metrics = self.sample_metrics()
        pressure = metrics["system_pressure"]
        if pressure == ResourcePressure.HIGH:
            return {"capture_delay_ms": 1200, "action_delay_ms": 700}
        elif pressure == ResourcePressure.MODERATE:
            return {"capture_delay_ms": 800, "action_delay_ms": 450}
        return {"capture_delay_ms": 400, "action_delay_ms": 300}

    def _estimate_model_memory(self, model_name: str) -> int:
        """Estimates model RAM footprint based on quantization size."""
        name_lower = model_name.lower()
        if "1b" in name_lower or "1.5b" in name_lower:
            return 1100  # ~1.1 GB RAM
        elif "3b" in name_lower:
            return 2200  # ~2.2 GB RAM
        elif "7b" or "8b" in name_lower:
            return 4500  # Risky on 6GB RAM
        return 1500

    def _get_system_memory(self) -> Tuple[int, int]:
        """Reads system RAM (total, available) in MB."""
        if self.is_windows:
            try:
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_mb = int(stat.ullTotalPhys / (1024 * 1024))
                    avail_mb = int(stat.ullAvailPhys / (1024 * 1024))
                    return total_mb, avail_mb
            except Exception as e:
                logger.warning("Windows memory query failed: %s", e)

        # Linux /proc/meminfo fallback
        if os.path.exists("/proc/meminfo"):
            try:
                mem = {}
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip().split()[0]
                            mem[key] = int(val)
                total_mb = mem.get("MemTotal", 6144000) // 1024
                avail_mb = mem.get("MemAvailable", mem.get("MemFree", 3072000)) // 1024
                return total_mb, avail_mb
            except Exception:
                pass

        # Safe fallback baseline
        return 6144, 3200

    def _get_process_memory(self) -> int:
        """Returns the Python process Resident Set Size in MB."""
        if os.path.exists("/proc/self/status"):
            try:
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            return int(parts[1]) // 1024
            except Exception:
                pass

        if self.is_windows:
            try:
                import ctypes.wintypes
                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ('cb', ctypes.wintypes.DWORD),
                        ('PageFaultCount', ctypes.wintypes.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t),
                    ]
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                h_process = ctypes.windll.kernel32.GetCurrentProcess()
                if ctypes.windll.psapi.GetProcessMemoryInfo(h_process, ctypes.byref(counters), ctypes.sizeof(counters)):
                    return int(counters.WorkingSetSize / (1024 * 1024))
            except Exception:
                pass

        return 45  # Standard modest baseline

    def _get_cpu_percent(self) -> float:
        """Estimates CPU utilization."""
        if os.path.exists("/proc/stat"):
            try:
                with open("/proc/stat", "r") as f:
                    line = f.readline()
                parts = [float(x) for x in line.split()[1:8]]
                idle = parts[3] + parts[4]
                total = sum(parts)
                now_tuple = (idle, total)
                if self._last_cpu_times:
                    d_idle = now_tuple[0] - self._last_cpu_times[0]
                    d_total = now_tuple[1] - self._last_cpu_times[1]
                    self._last_cpu_times = now_tuple
                    if d_total > 0:
                        return max(0.0, min(100.0, (1.0 - (d_idle / d_total)) * 100.0))
                self._last_cpu_times = now_tuple
                return 15.0
            except Exception:
                pass
        return 12.0
