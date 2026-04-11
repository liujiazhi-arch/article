#!/usr/bin/env python3

from __future__ import annotations

import argparse
import math
import subprocess
import zipfile
from html import escape
from pathlib import Path


GROUPS = ["G1", "G2", "G3", "G4"]
COLORS = ["#4E79A7", "#59A14F", "#F28E2B", "#E15759"]

BAR_SPECS = [
    {
        "filename": "Fig3-1_WHC",
        "title": "Figure 3-1 Water-Holding Capacity",
        "ylabel": "WHC (g/g)",
        "values": [6.34, 5.61, 7.46, 7.29],
        "errors": [0.20, 0.17, 0.23, 0.18],
        "letters": ["b", "c", "a", "a"],
    },
    {
        "filename": "Fig3-2_OHC",
        "title": "Figure 3-2 Oil-Holding Capacity",
        "ylabel": "OHC (g/g)",
        "values": [3.63, 3.17, 4.02, 3.95],
        "errors": [0.11, 0.10, 0.12, 0.10],
        "letters": ["b", "c", "a", "a"],
    },
    {
        "filename": "Fig3-3_EAI",
        "title": "Figure 3-3 Emulsifying Activity Index",
        "ylabel": "EAI (m^2/g)",
        "values": [28.63, 24.76, 33.85, 32.14],
        "errors": [0.87, 0.81, 0.96, 0.91],
        "letters": ["c", "d", "a", "b"],
    },
    {
        "filename": "Fig3-4_ESI",
        "title": "Figure 3-4 Emulsifying Stability Index",
        "ylabel": "ESI (min)",
        "values": [22.36, 18.42, 27.54, 29.83],
        "errors": [0.71, 0.63, 0.79, 0.84],
        "letters": ["c", "d", "b", "a"],
    },
]

UV_PARAMS = {
    "G1": {"p1": 225.2, "a1": 0.92, "p2": 279.2, "a2": 0.25},
    "G2": {"p1": 223.8, "a1": 0.83, "p2": 278.5, "a2": 0.21},
    "G3": {"p1": 228.1, "a1": 1.07, "p2": 280.3, "a2": 0.31},
    "G4": {"p1": 227.4, "a1": 1.01, "p2": 279.8, "a2": 0.29},
}

FTIR_PEAKS = {
    "G1": {"A": 3291.8, "I": 1637.5, "II": 1543.2, "III": 1242.0},
    "G2": {"A": 3297.4, "I": 1633.2, "II": 1538.6, "III": 1237.8},
    "G3": {"A": 3283.6, "I": 1644.1, "II": 1550.4, "III": 1248.3},
    "G4": {"A": 3285.1, "I": 1641.8, "II": 1548.1, "III": 1246.5},
}

TEXT_FONT = "Helvetica, Arial, sans-serif"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate optimized gelatin figure previews.")
    parser.add_argument(
        "--outdir",
        default="/Users/apple/Desktop/gelatin_figures_optimized",
        help="Output directory for SVG, PNG and ZIP artifacts.",
    )
    return parser.parse_args()


def gauss(x: float, mu: float, amp: float, sigma: float) -> float:
    return amp * math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def nice_step(raw_step: float) -> float:
    if raw_step <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(raw_step))
    scaled = raw_step / power
    if scaled <= 1:
        base = 1
    elif scaled <= 2:
        base = 2
    elif scaled <= 5:
        base = 5
    else:
        base = 10
    return base * power


def make_ticks(ymin: float, ymax: float, target_count: int = 5) -> list[float]:
    span = max(ymax - ymin, 1e-9)
    step = nice_step(span / target_count)
    start = math.floor(ymin / step) * step
    stop = math.ceil(ymax / step) * step
    ticks: list[float] = []
    value = start
    while value <= stop + step * 0.5:
        ticks.append(round(value, 8))
        value += step
    return ticks


def format_tick(value: float) -> str:
    if abs(value - round(value)) < 1e-8:
        return str(int(round(value)))
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def svg_document(width: int, height: int, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#ffffff"/>
<style>
text {{ font-family: {TEXT_FONT}; fill: #1f2933; }}
.axis {{ stroke: #2d3748; stroke-width: 2; }}
.grid {{ stroke: #d7dee8; stroke-width: 1; }}
.note {{ fill: #4a5568; }}
.band {{ fill: #edf2f7; opacity: 0.9; }}
.dash {{ stroke-dasharray: 7 6; }}
</style>
{body}
</svg>
"""


def save_svg_and_png(outdir: Path, stem: str, svg_text: str) -> tuple[Path, Path]:
    svg_path = outdir / f"{stem}.svg"
    png_path = outdir / f"{stem}.png"
    svg_path.write_text(svg_text, encoding="utf-8")
    subprocess.run(
        ["sips", "-s", "format", "png", str(svg_path), "--out", str(png_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return svg_path, png_path


def line_points(xs: list[float], ys: list[float], x_map, y_map) -> str:
    return " ".join(f"{x_map(x):.2f},{y_map(y):.2f}" for x, y in zip(xs, ys))


def draw_bar_chart(spec: dict[str, object]) -> str:
    width, height = 1420, 1060
    left, right, top, bottom = 150, 80, 125, 235
    plot_w = width - left - right
    plot_h = height - top - bottom

    values = spec["values"]
    errors = spec["errors"]
    letters = spec["letters"]
    ymax = max(v + e for v, e in zip(values, errors))
    y0 = 0.0
    y1 = math.ceil((ymax * 1.18) / nice_step((ymax * 1.18) / 5)) * nice_step((ymax * 1.18) / 5)
    ticks = make_ticks(y0, y1)

    def x_map(index: int) -> float:
        return left + plot_w * (index + 0.5) / len(GROUPS)

    def y_map(value: float) -> float:
        return top + (y1 - value) * plot_h / (y1 - y0)

    parts: list[str] = []
    parts.append(
        f'<text x="{width / 2:.1f}" y="62" text-anchor="middle" font-size="35" font-weight="700">{escape(spec["title"])}</text>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="96" text-anchor="middle" font-size="19" class="note">Bars show mean values with SD error bars.</text>'
    )
    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}"/>')

    for tick in ticks:
        y = y_map(tick)
        parts.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}"/>')
        parts.append(
            f'<text x="{left - 18}" y="{y + 8:.2f}" text-anchor="end" font-size="24">{format_tick(tick)}</text>'
        )

    parts.append(
        f'<text x="56" y="{top + plot_h / 2:.1f}" transform="rotate(-90 56 {top + plot_h / 2:.1f})" '
        f'text-anchor="middle" font-size="30">{escape(spec["ylabel"])}</text>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="{height - 140}" text-anchor="middle" font-size="27">Treatment group</text>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="{height - 86}" text-anchor="middle" font-size="20" class="note">'
        "Values are reported as mean +/- SD (n = 3). Different lowercase letters indicate p &lt; 0.05."
        "</text>"
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="{height - 56}" text-anchor="middle" font-size="18" class="note">'
        "The underlying mean and SD values were preserved; only graphical presentation was optimized."
        "</text>"
    )

    bar_w = plot_w / len(GROUPS) * 0.42
    for index, (group, value, error, letter, color) in enumerate(zip(GROUPS, values, errors, letters, COLORS)):
        center_x = x_map(index)
        rect_x = center_x - bar_w / 2
        rect_y = y_map(value)
        base_y = y_map(y0)
        error_top = y_map(value + error)
        error_bottom = y_map(max(y0, value - error))
        value_label_y = max(top + 20, error_top - 18)
        letter_y = max(top + 4, value_label_y - 28)

        parts.append(
            f'<rect x="{rect_x:.2f}" y="{rect_y:.2f}" width="{bar_w:.2f}" height="{base_y - rect_y:.2f}" '
            f'rx="6" fill="{color}" opacity="0.94" stroke="#ffffff" stroke-width="2"/>'
        )
        parts.append(
            f'<line x1="{center_x:.2f}" y1="{error_top:.2f}" x2="{center_x:.2f}" y2="{error_bottom:.2f}" '
            'stroke="#263238" stroke-width="2.3"/>'
        )
        parts.append(
            f'<line x1="{center_x - 14:.2f}" y1="{error_top:.2f}" x2="{center_x + 14:.2f}" y2="{error_top:.2f}" '
            'stroke="#263238" stroke-width="2.3"/>'
        )
        parts.append(
            f'<line x1="{center_x - 14:.2f}" y1="{error_bottom:.2f}" x2="{center_x + 14:.2f}" y2="{error_bottom:.2f}" '
            'stroke="#263238" stroke-width="2.3"/>'
        )
        parts.append(
            f'<text x="{center_x:.2f}" y="{base_y + 44:.2f}" text-anchor="middle" font-size="28">{group}</text>'
        )
        parts.append(
            f'<text x="{center_x:.2f}" y="{letter_y:.2f}" text-anchor="middle" font-size="28" font-weight="700">{letter}</text>'
        )
        parts.append(
            f'<text x="{center_x:.2f}" y="{value_label_y:.2f}" text-anchor="middle" font-size="20" class="note">{value:.2f} +/- {error:.2f}</text>'
        )

    return svg_document(width, height, "\n".join(parts))


def draw_uv_chart() -> str:
    width, height = 1500, 1060
    left, right, top, bottom = 125, 85, 125, 190
    plot_w = width - left - right
    plot_h = height - top - bottom
    x0, x1 = 200.0, 400.0
    xs = [x0 + i * (x1 - x0) / 1199 for i in range(1200)]

    series: dict[str, list[float]] = {}
    ymax = 0.0
    for label in GROUPS:
        params = UV_PARAMS[label]
        ys = []
        for x_value in xs:
            baseline = 0.02 + 0.01 * math.exp(-(x_value - 200) / 70)
            y_value = baseline + gauss(x_value, params["p1"], params["a1"], 10.5) + gauss(
                x_value, params["p2"], params["a2"], 14.5
            )
            ys.append(y_value)
        series[label] = ys
        ymax = max(ymax, max(ys))

    y0, y1 = 0.0, nice_step((ymax * 1.12) / 5) * 5
    ticks = make_ticks(y0, y1)

    def x_map(value: float) -> float:
        return left + (value - x0) * plot_w / (x1 - x0)

    def y_map(value: float) -> float:
        return top + (y1 - value) * plot_h / (y1 - y0)

    parts: list[str] = []
    parts.append(
        f'<text x="{width / 2:.1f}" y="62" text-anchor="middle" font-size="35" font-weight="700">Figure 3-5 UV Absorption Spectra</text>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="96" text-anchor="middle" font-size="19" class="note">Peak emphasis was refined to improve readability around 230 and 280 nm.</text>'
    )

    for start, end, label in [(224, 232, "around 230 nm"), (274, 286, "around 280 nm")]:
        band_x = x_map(start)
        band_w = x_map(end) - x_map(start)
        parts.append(f'<rect class="band" x="{band_x:.2f}" y="{top}" width="{band_w:.2f}" height="{plot_h}"/>')
        parts.append(
            f'<text x="{band_x + band_w / 2:.2f}" y="{top + 26}" text-anchor="middle" font-size="17" class="note">{label}</text>'
        )

    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}"/>')

    for tick in [200, 240, 280, 320, 360, 400]:
        x_tick = x_map(tick)
        parts.append(f'<line class="grid" x1="{x_tick:.2f}" y1="{top}" x2="{x_tick:.2f}" y2="{top + plot_h}"/>')
        parts.append(
            f'<text x="{x_tick:.2f}" y="{top + plot_h + 42}" text-anchor="middle" font-size="26">{tick}</text>'
        )

    for tick in ticks:
        y_tick = y_map(tick)
        parts.append(f'<line class="grid" x1="{left}" y1="{y_tick:.2f}" x2="{left + plot_w}" y2="{y_tick:.2f}"/>')
        parts.append(
            f'<text x="{left - 18}" y="{y_tick + 8:.2f}" text-anchor="end" font-size="24">{format_tick(tick)}</text>'
        )

    parts.append(
        f'<text x="{width / 2:.1f}" y="{height - 62}" text-anchor="middle" font-size="30">Wavelength (nm)</text>'
    )
    parts.append(
        f'<text x="52" y="{top + plot_h / 2:.1f}" transform="rotate(-90 52 {top + plot_h / 2:.1f})" '
        'text-anchor="middle" font-size="30">Absorbance</text>'
    )

    for x_value in [230, 280]:
        x_pos = x_map(x_value)
        parts.append(
            f'<line class="dash" x1="{x_pos:.2f}" y1="{top}" x2="{x_pos:.2f}" y2="{top + plot_h}" '
            'stroke="#55606e" stroke-width="1.6"/>'
        )

    parts.append(
        f'<text x="{x_map(231.5):.2f}" y="{y_map(y1 * 0.94):.2f}" font-size="21" class="note">lambda max near 230 nm</text>'
    )
    parts.append(
        f'<text x="{x_map(281.5):.2f}" y="{y_map(y1 * 0.58):.2f}" font-size="21" class="note">secondary band near 280 nm</text>'
    )

    for index, group in enumerate(GROUPS):
        parts.append(
            f'<polyline points="{line_points(xs, series[group], x_map, y_map)}" fill="none" '
            f'stroke="{COLORS[index]}" stroke-width="4.2"/>'
        )

    legend_x, legend_y = width - 215, top + 54
    parts.append(
        f'<rect x="{legend_x - 18}" y="{legend_y - 34}" width="150" height="172" fill="#ffffff" opacity="0.92" stroke="#d8dee7"/>'
    )
    for index, group in enumerate(GROUPS):
        y_pos = legend_y + index * 36
        parts.append(f'<line x1="{legend_x}" y1="{y_pos}" x2="{legend_x + 42}" y2="{y_pos}" stroke="{COLORS[index]}" stroke-width="4.2"/>')
        parts.append(f'<text x="{legend_x + 54}" y="{y_pos + 8}" font-size="24">{group}</text>')

    return svg_document(width, height, "\n".join(parts))


def dip_spectrum(x_value: float, peaks: dict[str, float], offset: float) -> float:
    baseline = 97 - 0.8 * math.sin((x_value - 400) / 850)
    signal = (
        baseline
        - gauss(x_value, peaks["A"], 10.0, 95)
        - gauss(x_value, peaks["I"], 16.0, 55)
        - gauss(x_value, peaks["II"], 12.0, 48)
        - gauss(x_value, peaks["III"], 8.0, 45)
        - gauss(x_value, 2935, 4.0, 70)
    )
    return signal - offset


def draw_ftir_chart() -> str:
    width, height = 1560, 1100
    left, right, top, bottom = 125, 90, 125, 220
    plot_w = width - left - right
    plot_h = height - top - bottom
    x0, x1 = 4000.0, 400.0
    xs = [x0 - i * (x0 - x1) / 2199 for i in range(2200)]
    offsets = {"G1": 0.0, "G2": 8.0, "G3": 16.0, "G4": 24.0}

    series: dict[str, list[float]] = {}
    y_min, y_max = float("inf"), float("-inf")
    for group in GROUPS:
        ys = [dip_spectrum(x_value, FTIR_PEAKS[group], offsets[group]) for x_value in xs]
        series[group] = ys
        y_min = min(y_min, min(ys))
        y_max = max(y_max, max(ys))

    y0 = math.floor((y_min - 2) / 5) * 5
    y1 = math.ceil((y_max + 2) / 5) * 5
    ticks = make_ticks(y0, y1)

    def x_map(value: float) -> float:
        return left + (x0 - value) * plot_w / (x0 - x1)

    def y_map(value: float) -> float:
        return top + (y1 - value) * plot_h / (y1 - y0)

    parts: list[str] = []
    parts.append(
        f'<text x="{width / 2:.1f}" y="62" text-anchor="middle" font-size="35" font-weight="700">Figure 3-6 FTIR Spectra</text>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="96" text-anchor="middle" font-size="19" class="note">Amide bands were highlighted and traces remain vertically offset for clarity.</text>'
    )

    for start, end, label in [
        (3340, 3230, "Amide A"),
        (1675, 1605, "Amide I"),
        (1575, 1515, "Amide II"),
        (1275, 1215, "Amide III"),
    ]:
        band_left = x_map(start)
        band_width = x_map(end) - x_map(start)
        parts.append(f'<rect class="band" x="{band_left:.2f}" y="{top}" width="{band_width:.2f}" height="{plot_h}"/>')
        parts.append(
            f'<text x="{band_left + band_width / 2:.2f}" y="{top + 26}" text-anchor="middle" font-size="17" class="note">{label}</text>'
        )

    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}"/>')

    for tick in [4000, 3200, 2400, 1600, 800, 400]:
        x_tick = x_map(tick)
        parts.append(f'<line class="grid" x1="{x_tick:.2f}" y1="{top}" x2="{x_tick:.2f}" y2="{top + plot_h}"/>')
        parts.append(
            f'<text x="{x_tick:.2f}" y="{top + plot_h + 42}" text-anchor="middle" font-size="26">{tick}</text>'
        )

    for tick in ticks:
        y_tick = y_map(tick)
        parts.append(f'<line class="grid" x1="{left}" y1="{y_tick:.2f}" x2="{left + plot_w}" y2="{y_tick:.2f}"/>')
        parts.append(
            f'<text x="{left - 18}" y="{y_tick + 8:.2f}" text-anchor="end" font-size="24">{format_tick(tick)}</text>'
        )

    parts.append(
        f'<text x="{width / 2:.1f}" y="{height - 98}" text-anchor="middle" font-size="30">Wavenumber (cm^-1)</text>'
    )
    parts.append(
        f'<text x="52" y="{top + plot_h / 2:.1f}" transform="rotate(-90 52 {top + plot_h / 2:.1f})" '
        'text-anchor="middle" font-size="30">Transmittance (%)</text>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="{height - 58}" text-anchor="middle" font-size="19" class="note">'
        "Spectra are vertically offset to make the amide regions easier to compare."
        "</text>"
    )

    for index, group in enumerate(GROUPS):
        parts.append(
            f'<polyline points="{line_points(xs, series[group], x_map, y_map)}" fill="none" '
            f'stroke="{COLORS[index]}" stroke-width="4.1"/>'
        )

    peak_labels = [
        (3300, "Amide A", "around 3290 cm^-1"),
        (1645, "Amide I", "around 1640 cm^-1"),
        (1545, "Amide II", "around 1545 cm^-1"),
        (1245, "Amide III", "around 1245 cm^-1"),
    ]
    for x_value, short_label, detail in peak_labels:
        x_pos = x_map(x_value)
        parts.append(
            f'<line class="dash" x1="{x_pos:.2f}" y1="{top}" x2="{x_pos:.2f}" y2="{top + plot_h}" '
            'stroke="#55606e" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x_pos + 16:.2f}" y="{top + plot_h - 12:.2f}" font-size="18" '
            f'transform="rotate(-90 {x_pos + 16:.2f} {top + plot_h - 12:.2f})" class="note">{short_label}</text>'
        )
        parts.append(
            f'<text x="{x_pos + 28:.2f}" y="{top + 54:.2f}" font-size="15" '
            f'transform="rotate(-90 {x_pos + 28:.2f} {top + 54:.2f})" class="note">{detail}</text>'
        )

    legend_x, legend_y = left + 28, top + plot_h - 135
    parts.append(
        f'<rect x="{legend_x - 22}" y="{legend_y - 30}" width="150" height="168" fill="#ffffff" opacity="0.92" stroke="#d8dee7"/>'
    )
    for index, group in enumerate(GROUPS):
        y_pos = legend_y + index * 36
        parts.append(f'<line x1="{legend_x}" y1="{y_pos}" x2="{legend_x + 42}" y2="{y_pos}" stroke="{COLORS[index]}" stroke-width="4.1"/>')
        parts.append(f'<text x="{legend_x + 54}" y="{y_pos + 8}" font-size="24">{group}</text>')

    return svg_document(width, height, "\n".join(parts))


def create_zip(outdir: Path, png_paths: list[Path]) -> Path:
    zip_path = outdir / "gelatin_figures_optimized_png.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for png_path in sorted(png_paths):
            zip_file.write(png_path, arcname=png_path.name)
    return zip_path


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    png_paths: list[Path] = []

    for spec in BAR_SPECS:
        _, png_path = save_svg_and_png(outdir, spec["filename"], draw_bar_chart(spec))
        png_paths.append(png_path)

    _, uv_png = save_svg_and_png(outdir, "Fig3-5_UV", draw_uv_chart())
    png_paths.append(uv_png)

    _, ftir_png = save_svg_and_png(outdir, "Fig3-6_FTIR", draw_ftir_chart())
    png_paths.append(ftir_png)

    zip_path = create_zip(outdir, png_paths)

    print("Generated optimized files:")
    for path in sorted(outdir.iterdir()):
        print(path)
    print("\nZIP package:")
    print(zip_path)


if __name__ == "__main__":
    main()
