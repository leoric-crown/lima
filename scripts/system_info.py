#!/usr/bin/env python3
"""System information gathering for benchmark profiling."""

import ctypes
import json
import os
import platform
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass
class GpuInfo:
    name: str
    vram_mb: int
    driver_version: str | None = None


@dataclass
class SystemInfo:
    timestamp: str
    hostname: str
    os: str
    os_version: str
    platform: str
    cpu: str
    cpu_cores_physical: int
    cpu_cores_logical: int
    ram_gb: float
    gpu: GpuInfo | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def get_cpu_info_windows() -> tuple[str, int, int]:
    """Get CPU info on Windows using ctypes and registry."""
    import winreg

    cpu_name = "Unknown"
    physical_cores = os.cpu_count() or 1
    logical_cores = os.cpu_count() or 1

    # Get CPU name from registry
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        )
        cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        winreg.CloseKey(key)
    except Exception:
        pass

    # Get core counts using ctypes
    try:
        # Use GetLogicalProcessorInformationEx for accurate counts
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32

        # First, get physical core count via environment variable (most reliable)
        physical_cores = int(os.environ.get("NUMBER_OF_PROCESSORS", logical_cores))

        # Try to get actual physical vs logical using GetSystemInfo
        class SYSTEM_INFO(ctypes.Structure):
            _fields_ = [
                ("wProcessorArchitecture", wintypes.WORD),
                ("wReserved", wintypes.WORD),
                ("dwPageSize", wintypes.DWORD),
                ("lpMinimumApplicationAddress", ctypes.c_void_p),
                ("lpMaximumApplicationAddress", ctypes.c_void_p),
                ("dwActiveProcessorMask", ctypes.c_size_t),
                ("dwNumberOfProcessors", wintypes.DWORD),
                ("dwProcessorType", wintypes.DWORD),
                ("dwAllocationGranularity", wintypes.DWORD),
                ("wProcessorLevel", wintypes.WORD),
                ("wProcessorRevision", wintypes.WORD),
            ]

        sysinfo = SYSTEM_INFO()
        kernel32.GetSystemInfo(ctypes.byref(sysinfo))
        logical_cores = sysinfo.dwNumberOfProcessors

        # Physical cores: try reading from registry (count of CPU keys)
        try:
            cpu_count = 0
            i = 0
            while True:
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        rf"HARDWARE\DESCRIPTION\System\CentralProcessor\{i}"
                    )
                    winreg.CloseKey(key)
                    cpu_count += 1
                    i += 1
                except WindowsError:
                    break
            # This gives logical processors, estimate physical as half (assuming HT)
            if cpu_count > 0:
                # Check if hyperthreading by comparing to logical
                if logical_cores == cpu_count:
                    physical_cores = logical_cores // 2 if logical_cores > 1 else 1
                else:
                    physical_cores = cpu_count
        except Exception:
            physical_cores = logical_cores // 2 if logical_cores > 1 else 1

    except Exception:
        pass

    return cpu_name.strip(), physical_cores, logical_cores


def get_cpu_info_linux() -> tuple[str, int, int]:
    """Get CPU info on Linux."""
    cpu_name = "Unknown"
    physical_cores = os.cpu_count() or 1
    logical_cores = os.cpu_count() or 1

    try:
        with open("/proc/cpuinfo") as f:
            content = f.read()
            for line in content.split("\n"):
                if line.startswith("model name"):
                    cpu_name = line.split(":")[1].strip()
                    break

            # Count physical cores (unique core ids per physical id)
            physical_ids = set()
            core_ids = set()
            current_physical = None
            for line in content.split("\n"):
                if line.startswith("physical id"):
                    current_physical = line.split(":")[1].strip()
                    physical_ids.add(current_physical)
                elif line.startswith("core id") and current_physical is not None:
                    core_ids.add((current_physical, line.split(":")[1].strip()))

            if core_ids:
                physical_cores = len(core_ids)
            logical_cores = os.cpu_count() or 1
    except Exception:
        pass

    return cpu_name, physical_cores, logical_cores


def get_cpu_info_macos() -> tuple[str, int, int]:
    """Get CPU info on macOS."""
    cpu_name = platform.processor() or "Unknown"
    physical_cores = os.cpu_count() or 1
    logical_cores = os.cpu_count() or 1

    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            cpu_name = result.stdout.strip()

        result = subprocess.run(
            ["sysctl", "-n", "hw.physicalcpu"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            physical_cores = int(result.stdout.strip())

        result = subprocess.run(
            ["sysctl", "-n", "hw.logicalcpu"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            logical_cores = int(result.stdout.strip())
    except Exception:
        pass

    return cpu_name, physical_cores, logical_cores


def get_cpu_info() -> tuple[str, int, int]:
    """Get CPU name and core counts (cross-platform)."""
    if sys.platform == "win32":
        return get_cpu_info_windows()
    elif sys.platform == "darwin":
        return get_cpu_info_macos()
    else:
        return get_cpu_info_linux()


def get_ram_gb_windows() -> float:
    """Get total RAM on Windows using ctypes."""
    try:
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        meminfo = MEMORYSTATUSEX()
        meminfo.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(meminfo))
        return meminfo.ullTotalPhys / (1024**3)
    except Exception:
        return 0.0


def get_ram_gb_linux() -> float:
    """Get total RAM on Linux."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb / (1024**2)
    except Exception:
        pass
    return 0.0


def get_ram_gb_macos() -> float:
    """Get total RAM on macOS."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) / (1024**3)
    except Exception:
        pass
    return 0.0


def get_ram_gb() -> float:
    """Get total RAM in GB (cross-platform)."""
    if sys.platform == "win32":
        return get_ram_gb_windows()
    elif sys.platform == "darwin":
        return get_ram_gb_macos()
    else:
        return get_ram_gb_linux()


def get_nvidia_gpu() -> GpuInfo | None:
    """Get NVIDIA GPU info using nvidia-smi."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            line = result.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                return GpuInfo(
                    name=parts[0],
                    vram_mb=int(parts[1]),
                    driver_version=parts[2],
                )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def get_audio_duration(file_path: Path) -> float | None:
    """Get audio duration using mutagen (pure Python) or ffprobe as fallback."""
    # Try mutagen first (pure Python, no external dependencies)
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(file_path)
        if audio is not None and audio.info is not None:
            return audio.info.length
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback to ffprobe
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def get_system_info() -> SystemInfo:
    """Gather all system information."""
    cpu_name, physical_cores, logical_cores = get_cpu_info()

    return SystemInfo(
        timestamp=datetime.now(timezone.utc).isoformat(),
        hostname=socket.gethostname(),
        os=platform.system(),
        os_version=platform.version(),
        platform=platform.platform(),
        cpu=cpu_name,
        cpu_cores_physical=physical_cores,
        cpu_cores_logical=logical_cores,
        ram_gb=round(get_ram_gb(), 1),
        gpu=get_nvidia_gpu(),
    )


def main():
    """Test system info gathering."""
    print("=" * 60)
    print("SYSTEM INFORMATION")
    print("=" * 60)

    info = get_system_info()

    print(f"\nTimestamp: {info.timestamp}")
    print(f"Hostname: {info.hostname}")
    print(f"OS: {info.os} ({info.os_version})")
    print(f"Platform: {info.platform}")
    print(f"CPU: {info.cpu}")
    print(f"Cores: {info.cpu_cores_physical} physical, {info.cpu_cores_logical} logical")
    print(f"RAM: {info.ram_gb} GB")

    if info.gpu:
        print(f"GPU: {info.gpu.name}")
        print(f"VRAM: {info.gpu.vram_mb} MB ({info.gpu.vram_mb / 1024:.1f} GB)")
        print(f"Driver: {info.gpu.driver_version}")
    else:
        print("GPU: Not detected (no NVIDIA GPU or nvidia-smi not available)")

    # Test audio duration
    print("\n" + "=" * 60)
    print("AUDIO FILE DURATIONS")
    print("=" * 60)

    audio_dir = Path(__file__).parent.parent / "data" / "audio"
    audio_files = sorted(
        [f for f in audio_dir.glob("*") if f.is_file() and f.suffix.lower() in (".mp3", ".flac", ".wav", ".m4a")],
        key=lambda f: f.stat().st_size
    )

    for f in audio_files:
        duration = get_audio_duration(f)
        size_mb = f.stat().st_size / (1024 * 1024)
        if duration:
            minutes = int(duration // 60)
            seconds = duration % 60
            print(f"  {f.name}: {size_mb:.2f} MB, {minutes}m {seconds:.1f}s ({duration:.1f}s)")
        else:
            print(f"  {f.name}: {size_mb:.2f} MB, duration unknown (ffprobe not available?)")

    # Output as JSON
    print("\n" + "=" * 60)
    print("JSON OUTPUT")
    print("=" * 60)
    print(json.dumps(info.to_dict(), indent=2))


if __name__ == "__main__":
    main()
