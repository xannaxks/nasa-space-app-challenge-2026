import io

with io.open("routing.py", encoding="utf-8") as f:
    src = f.read()
old = (
    '        raise IndexError("Target is outside the raster")\n'
    '        if not math.isfinite(result.distance[row, col]):\n'
    '        raise ValueError("Target is unreachable")\n'
)
new = (
    '        raise IndexError("Target is outside the raster")\n'
    '    if not math.isfinite(result.distance[row, col]):\n'
    '        raise ValueError("Target is unreachable")\n'
)
assert old in src, "anchor not found"
src = src.replace(old, new)
with io.open("routing.py", "w", encoding="utf-8", newline="") as f:
    f.write(src)
print("fixed")
