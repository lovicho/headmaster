import os
import sys
import logging

logger = logging.getLogger(__name__)

def get_total_ram_gb() -> float:
    try:
        if sys.platform == "win32":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_uint32),
                    ('dwMemoryLoad', ctypes.c_uint32),
                    ('ullTotalPhys', ctypes.c_uint64),
                    ('ullAvailPhys', ctypes.c_uint64),
                    ('ullTotalPageFile', ctypes.c_uint64),
                    ('ullAvailPageFile', ctypes.c_uint64),
                    ('ullTotalVirtual', ctypes.c_uint64),
                    ('ullAvailVirtual', ctypes.c_uint64),
                    ('ullAvailExtendedVirtual', ctypes.c_uint64),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullTotalPhys / (1024**3)
        elif sys.platform.startswith("linux"):
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        kb = int(line.split()[1])
                        return kb / (1024**2)
        elif sys.platform == "darwin":
            import subprocess
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"])
            return int(out.strip()) / (1024**3)
    except Exception as e:
        logger.debug(f"Failed to fetch system RAM: {e}")
    
    # Fallback to a standard developer machine baseline
    return 16.0

def get_concurrency_limit() -> int:
    """
    Returns the dynamically computed concurrency limit based on system RAM
    and the user's requested mode (HEADMASTER_CONCURRENCY_MODE).
    """
    mode = os.environ.get("HEADMASTER_CONCURRENCY_MODE", "safe").lower()
    ram_gb = get_total_ram_gb()
    
    if mode == "max":
        # Max mode pushes the system (e.g. ~100 max agents for 16GB RAM)
        limit = int(ram_gb * 6.25)
        return max(30, min(500, limit))
    else:
        # Safe mode defaults to minimal footprint (e.g. ~32 agents for 16GB RAM)
        limit = int(ram_gb * 2.0)
        return max(10, min(100, limit))

# Initialize cache at module load
DEFAULT_CONCURRENCY_LIMIT = get_concurrency_limit()
