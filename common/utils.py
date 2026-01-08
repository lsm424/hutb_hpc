def Unit2int(unit: str) -> float:
    unit = unit.strip()
    "TiB, GiB, MiB, KiB转GiB"
    if unit.endswith('TiB'):
        return int(unit[:-3]) * 1024
    elif unit.endswith('GiB'):
        return int(unit[:-3])
    elif unit.endswith('MiB'):
        return int(unit[:-3]) * 1024 * 1024
    elif unit.endswith('KiB'):
        return int(unit[:-3]) * 1024
