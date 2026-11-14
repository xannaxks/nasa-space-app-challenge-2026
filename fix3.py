import io

with io.open("api.py", encoding="utf-8") as f:
    src = f.read()
old = (
    '        "percentiles": {str(p): float(np.percentile(finite, p)) for p in (2, 5, 25, 50, 75, 95, 98)},\n'
    '    }\n'
    '    logger.info("map_info: %s done in %.2fs", key, time.perf_counter() - started)\n'
    '    return {\n'
)
new = (
    '        "percentiles": {str(p): float(np.percentile(finite, p)) for p in (2, 5, 25, 50, 75, 95, 98)},\n'
    '    }\n'
    '    logger.info("map_info: %s done in %.2fs", key, time.perf_counter() - started)\n'
    '    return stats\n'
)
assert old in src, "anchor not found"
src = src.replace(old, new)
old2 = (
    '    finite = arr[np.isfinite(arr)]\n'
    '    if finite.size == 0:\n'
    '        raise HTTPException(status_code=500, detail=f"layer {key!r} has no finite values")\n'
    '    return {\n'
)
new2 = (
    '    finite = arr[np.isfinite(arr)]\n'
    '    if finite.size == 0:\n'
    '        raise HTTPException(status_code=500, detail=f"layer {key!r} has no finite values")\n'
    '    stats = {\n'
)
assert old2 in src, "anchor2 not found"
src = src.replace(old2, new2)
with io.open("api.py", "w", encoding="utf-8", newline="") as f:
    f.write(src)
print("map_info fixed")
