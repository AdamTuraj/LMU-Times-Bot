# MIT License
#
# Copyright (c) 2026 Adam Turaj
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import io
import logging
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")

logger = logging.getLogger(__name__)

COLUMNS = [
    "Class\nPos.",
    "Pos.",
    "Driver Name",
    "Car Model",
    "Sector 1",
    "Sector 2",
    "Sector 3",
    "Best Lap",
    "Delta",
]

BACKGROUND_COLOR = "#1e1e1e"
HEADER_COLOR = "#2a2a2a"
GOLD_COLOR = "#B8860B"
SILVER_COLOR = "#808080"
BRONZE_COLOR = "#8B4513"
FASTEST_SECTOR_COLOR = "#9932CC"
BORDER_COLOR = "#333333"
TEXT_COLOR = "#ffffff"

CLASS_COLORS = {
    "GT3": "#1a3a1a",
    "GTE": "#3a2a1a",
    "LMP3": "#2a1a3a",
    "LMP2": "#1a2a3a",
    "Hyper": "#3a1a1a"
}


def adjust_brightness(hex_color: str, factor: float) -> str:
    """Adjust the brightness of a hex color."""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def format_time(time: float) -> str:
    minutes = int(time // 60)
    seconds = time % 60
    return f"{minutes}:{seconds:06.3f}"


def format_sector(time: float | None) -> str:
    if time is None:
        return "-"
    return f"{time:.3f}"


def format_data(data: list[dict[str, Any]], show_technical: bool = True) -> list[list[Any]]:
    if not data:
        logger.warning("No data provided to format_data")
        return []

    sorted_data = sorted(data, key=lambda x: x["lap_time"])
    
    # Convert sectors to floats early and filter if not showing technical
    for driver in sorted_data:
        sector1 = driver.get("sector1")
        sector2 = driver.get("sector2")
        driver["sector1"] = float(sector1) if sector1 is not None else -1
        driver["sector2"] = float(sector2) if sector2 is not None else -1
        
        # Normalize class name
        if driver.get("car_class") == "LMP2_ELMS":
            driver["car_class"] = "LMP2"
    
    # Filter out invalid laps if not showing technical
    if not show_technical:
        sorted_data = [d for d in sorted_data if d["sector1"] != -1 and d["sector2"] != -1]
    
    # Calculate class positions AFTER filtering
    class_leaders = {}
    class_tracker = {"GT3": 0, "GTE": 0, "LMP3": 0, "LMP2": 0, "Hyper": 0}
    for driver in sorted_data:
        car_class = driver.get("car_class")
        class_tracker[car_class] += 1
        driver["class_pos"] = class_tracker[car_class]

        if car_class not in class_leaders:
            class_leaders[car_class] = driver["lap_time"]

    formatted = []
    for pos, driver in enumerate(sorted_data, 1):
        car_class = driver.get("car_class")
        class_leader_time = class_leaders.get(car_class, driver["lap_time"])
        delta = f"+{driver['lap_time'] - class_leader_time:.3f}" if driver["lap_time"] > class_leader_time else "-"
        class_pos = driver.get("class_pos", 0)

        sector1 = driver["sector1"]
        sector2 = driver["sector2"]
        lap_time = driver["lap_time"]

        # Process sectors based on show_technical
        if show_technical:
            if sector1 == -1 and sector2 > 0:
                # Sector 1 is invalid. Sector 1 and 2 cannot be shown but sector 3 can be calculated
                sector3 = format_sector(lap_time - sector2)
                sector1_str = "-"
                sector2_str = "-"
            elif sector2 == -1 and sector1 > 0:
                # Sector 2 is invalid. Sector 2 and 3 cannot be shown but sector 1 can be shown
                sector1_str = format_sector(sector1)
                sector2_str = "-"
                sector3 = "-"
            elif sector1 == -1 and sector2 == -1:
                # Both sectors are invalid somehow. Show dashes for all sectors
                sector1_str = "-"
                sector2_str = "-"
                sector3 = "-"
            else:
                # All sectors valid, calculate sector 3
                sector1_str = format_sector(sector1)
                sector2_str = format_sector(sector2 - sector1)
                sector3 = format_sector(lap_time - sector2)
        else:
            # All sectors are valid (filtered above)
            sector1_str = format_sector(sector1)
            sector2_str = format_sector(sector2 - sector1)
            sector3 = format_sector(lap_time - sector2)

        formatted.append([
            class_pos,
            pos,
            driver["driver_name"],
            driver["car"],
            sector1_str,
            sector2_str,
            sector3,
            format_time(lap_time),
            delta,
            car_class,
            class_pos
        ])
    
    logger.debug("Formatted %d lap time entries", len(formatted))
    return formatted


def gen_image(data: list[list[Any]], show_technical: bool) -> io.BytesIO:
    logger.debug("Generating leaderboard image with %d entries", len(data))
    
    fastest_splits = _find_fastest_sectors(data)
    
    class_pos = [row[-1] for row in data]
    car_classes = [row[-2] for row in data]
    table_data = [row[:-2] for row in data]
    
    df = pd.DataFrame(table_data, columns=COLUMNS)

    row_count = len(table_data) + 1
    row_height = 0.55
    fig_height = max(row_count * row_height, 2)

    fig, ax = plt.subplots(figsize=(18, fig_height), dpi=150)
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)
    ax.axis("off")

    col_widths = [0.04, 0.04, 0.20, 0.24, 0.09, 0.09, 0.09, 0.11, 0.10]

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="center",
        loc="center",
        colWidths=col_widths,
    )

    table.auto_set_font_size(False)
    table.set_fontsize(16)
    table.scale(1.0, 2.5)

    _style_table_cells(table, car_classes, class_pos)
    _highlight_fastest_sectors(table, table_data, fastest_splits)

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    image_stream = io.BytesIO()
    plt.savefig(
        image_stream,
        format="png",
        bbox_inches="tight",
        pad_inches=0.1,
        facecolor=fig.get_facecolor(),
    )
    image_stream.seek(0)
    plt.close(fig)

    logger.debug("Leaderboard image generated successfully")
    return image_stream


def _find_fastest_sectors(data: list[list[Any]]) -> list[float]:
    fastest_splits = [float("inf"), float("inf"), float("inf")]
    for driver in data:
        for i in range(4, 7):
            try:
                val = float(driver[i])
                if val > 0 and val < fastest_splits[i - 4]:
                    fastest_splits[i - 4] = val
            except (ValueError, TypeError):
                pass
    return fastest_splits


def _style_table_cells(table: Any, car_classes: list[str], class_pos: list[int]) -> None:
    for (i, j), cell in table.get_celld().items():
        cell.set_edgecolor(BORDER_COLOR)
        cell.set_linewidth(1.5)
        cell.set_text_props(
            fontfamily="DejaVu Sans",
            fontweight="bold",
            verticalalignment="center",
        )

        if i == 0:
            cell.set_facecolor(HEADER_COLOR)
            cell.set_text_props(color=TEXT_COLOR, fontweight="bold", fontsize=14)
        else:
            car_class = car_classes[i - 1] if i <= len(car_classes) else "LMGT3"
            base_color = CLASS_COLORS.get(car_class, "#252525")
            
            brightness_factor = 1.05 if j % 2 == 0 else 0.95
            row_color = adjust_brightness(base_color, brightness_factor)
            
            cell.set_facecolor(row_color)
            cell.set_text_props(color=TEXT_COLOR, fontweight="bold")
            
            if j == 0:
                if class_pos[i - 1] == 1:
                    cell.set_facecolor(GOLD_COLOR)
                elif class_pos[i - 1] == 2:
                    cell.set_facecolor(SILVER_COLOR)
                elif class_pos[i - 1] == 3:
                    cell.set_facecolor(BRONZE_COLOR)


def _highlight_fastest_sectors(
    table: Any, data: list[list[Any]], fastest_splits: list[float]
) -> None:
    for col_idx in range(4, 7):
        for row_idx in range(1, len(data) + 1):
            cell = table[row_idx, col_idx]
            try:
                cell_val = float(cell.get_text().get_text())
                if cell_val == fastest_splits[col_idx - 4]:
                    cell.set_facecolor(FASTEST_SECTOR_COLOR)
                    cell.set_text_props(color=TEXT_COLOR, fontweight="bold")
            except (ValueError, TypeError):
                pass
