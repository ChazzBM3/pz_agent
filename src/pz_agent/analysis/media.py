from __future__ import annotations

from pathlib import Path


def create_placeholder_plot(path: Path, title: str, points: list[dict] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"PLOT: {title}",
        "This is a placeholder plot artifact.",
        "Replace with matplotlib/plotly output in the next implementation step.",
        "",
        "POINTS:",
    ]
    for point in points or []:
        lines.append(str(point))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
