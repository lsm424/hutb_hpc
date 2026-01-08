def Unit2int(unit: str) -> float:
    unit = unit.strip()
    "TiB, GiB, MiB, KiB转GiB"
    if unit.endswith('TiB'):
        return float(unit[:-3]) * 1024
    elif unit.endswith('GiB'):
        return float(unit[:-3])
    elif unit.endswith('MiB'):
        return float(unit[:-3]) * 1024 * 1024
    elif unit.endswith('KiB'):
        return float(unit[:-3]) * 1024

def search_params(search: str) -> dict:
    parameters = {}
    search = search.lstrip('?')
    try:
        for slice in search.split("&"):
            try:
                x, y = slice.split("=")
                parameters[x] = y
            except:
                pass
    except:
        pass
    return parameters