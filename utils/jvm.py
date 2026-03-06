def get_system_ram_mb() -> int:
    try:
        import psutil
        return int(psutil.virtual_memory().total / 1024 / 1024)
    except ImportError:
        return 8192


def get_max_ram_mb() -> int:
    return int(get_system_ram_mb() * 0.75)


def get_default_jvm_args(ram_mb: int) -> list:
    xmx = ram_mb
    xms = max(512, ram_mb // 2)
    return [
        f"-Xmx{xmx}M", f"-Xms{xms}M",
        "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled",
        "-XX:MaxGCPauseMillis=200", "-XX:+UnlockExperimentalVMOptions",
        "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
        "-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40",
        "-XX:G1HeapRegionSize=8M", "-XX:G1ReservePercent=20",
        "-XX:G1HeapWastePercent=5", "-XX:G1MixedGCCountTarget=4",
        "-XX:InitiatingHeapOccupancyPercent=15",
        "-XX:G1MixedGCLiveThresholdPercent=90",
        "-XX:G1RSetUpdatingPauseTimePercent=5",
        "-XX:SurvivorRatio=32", "-XX:+PerfDisableSharedMem",
        "-XX:MaxTenuringThreshold=1",
    ]


def args_to_string(args: list) -> str:
    return " ".join(args)


def string_to_args(s: str) -> list:
    return [a for a in s.split() if a]
