import io

with io.open("api.py", encoding="utf-8") as f:
    src = f.read()
orig = src
fixes = [
    (
        "        end_ref = CellRef(row=points[b][0], col=points[b][1])\n                if not math.isfinite(cost):",
        "        end_ref = CellRef(row=points[b][0], col=points[b][1])\n        if not math.isfinite(cost):",
    ),
    (
        "            warnings.append(f\"leg {a}->{b} is unreachable under this cost model\")\n        logger.warning(\"route: leg",
        "            warnings.append(f\"leg {a}->{b} is unreachable under this cost model\")\n            logger.warning(\"route: leg",
    ),
    (
        "                           a, b, tuple(points[a]), tuple(points[b]))\n            continue",
        "                           a, b, tuple(points[a]), tuple(points[b]))\n            continue",
    ),
]
applied = 0
for old, new in fixes:
    if old in src:
        src = src.replace(old, new)
        applied += 1
    else:
        print("NOT FOUND:", old[:70].replace("\n", "\\n"))
if src != orig:
    with io.open("api.py", "w", encoding="utf-8", newline="") as f:
        f.write(src)
print("applied:", applied)
