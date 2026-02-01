import io
import logging
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

# Use non-interactive backend for server environments
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# Table column headers
COLUMNS = [
    "Pos.",
    "Driver Name",
    "Car Model",
    "Sector 1",
    "Sector 2",
    "Sector 3",
    "Best Lap",
    "Delta",
]

# Table styling constants
BACKGROUND_COLOR = "#1e1e1e"
HEADER_COLOR = "#2a2a2a"
GOLD_COLOR = "#B8860B"
SILVER_COLOR = "#808080"
BRONZE_COLOR = "#8B4513"
FASTEST_SECTOR_COLOR = "#9932CC"
BORDER_COLOR = "#333333"
TEXT_COLOR = "#ffffff"


def format_time(time: float) -> str:
    """Format time from seconds to M:SS.mmm format.
    
    Args:
        time: Time in seconds.
        
    Returns:
        Formatted time string.
    """
    minutes = int(time // 60)
    seconds = time % 60
    return f"{minutes}:{seconds:06.3f}"


def format_sector(time: float | None) -> str:
    """Format sector time for display.
    
    Args:
        time: Sector time in seconds, or None if not available.
        
    Returns:
        Formatted sector time or '-' if not available.
    """
    if time is None:
        return "-"
    return f"{time:.3f}"


def format_data(data: list[dict[str, Any]]) -> list[list[Any]]:
    """Format lap time data for table display.
    
    Args:
        data: List of lap time dictionaries from the database.
        
    Returns:
        Formatted data ready for table generation.
    """
    if not data:
        logger.warning("No data provided to format_data")
        return []

    sorted_data = sorted(data, key=lambda x: x["lap_time"])
    fastest_time = sorted_data[0]["lap_time"]

    formatted = [
        [
            pos,
            driver["driver_name"],
            driver["car"],
            format_sector(driver.get("sector1")),
            format_sector(driver.get("sector2")),
            format_sector(driver.get("sector3")),
            format_time(driver["lap_time"]),
            f"+{driver['lap_time'] - fastest_time:.3f}" if pos > 1 else "-",
        ]
        for pos, driver in enumerate(sorted_data, 1)
    ]
    
    logger.debug("Formatted %d lap time entries", len(formatted))
    return formatted


def gen_image(data: list[list[Any]]) -> io.BytesIO:
    """Generate a leaderboard image from formatted lap time data.
    
    Args:
        data: Formatted lap time data from format_data().
        
    Returns:
        BytesIO stream containing the PNG image.
    """
    logger.debug("Generating leaderboard image with %d entries", len(data))
    
    # Find fastest sectors for highlighting
    fastest_splits = _find_fastest_sectors(data)

    df = pd.DataFrame(data, columns=COLUMNS)

    # Calculate figure dimensions
    row_count = len(data) + 1
    row_height = 0.55
    fig_height = max(row_count * row_height, 2)

    # Create figure
    fig, ax = plt.subplots(figsize=(18, fig_height), dpi=150)
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)
    ax.axis("off")

    col_widths = [0.04, 0.22, 0.20, 0.10, 0.10, 0.10, 0.12, 0.10]

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

    # Apply styling to all cells
    _style_table_cells(table, len(data))
    
    # Highlight fastest sectors
    _highlight_fastest_sectors(table, data, fastest_splits)

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    # Save to buffer
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
    """Find the fastest time for each sector.
    
    Args:
        data: Formatted lap time data.
        
    Returns:
        List of fastest times for sectors 1, 2, and 3.
    """
    fastest_splits = [float("inf"), float("inf"), float("inf")]
    for driver in data:
        for i in range(3, 6):  # Sector columns (3, 4, 5)
            try:
                val = float(driver[i])
                if val > 0 and val < fastest_splits[i - 3]:
                    fastest_splits[i - 3] = val
            except (ValueError, TypeError):
                pass
    return fastest_splits


def _style_table_cells(table: Any, row_count: int) -> None:
    """Apply styling to table cells.
    
    Args:
        table: Matplotlib table object.
        row_count: Number of data rows (excluding header).
    """
    for (i, j), cell in table.get_celld().items():
        cell.set_edgecolor(BORDER_COLOR)
        cell.set_linewidth(1.5)
        cell.set_text_props(
            fontfamily="DejaVu Sans",
            fontweight="bold",
            verticalalignment="center",
        )

        if i == 0:  # Header row
            cell.set_facecolor(HEADER_COLOR)
            cell.set_text_props(color=TEXT_COLOR, fontweight="bold", fontsize=14)
        elif i == 1:  # First place (Gold)
            cell.set_facecolor(GOLD_COLOR)
            cell.set_text_props(color=TEXT_COLOR, fontweight="bold")
        elif i == 2:  # Second place (Silver)
            cell.set_facecolor(SILVER_COLOR)
            cell.set_text_props(color=TEXT_COLOR, fontweight="bold")
        elif i == 3:  # Third place (Bronze)
            cell.set_facecolor(BRONZE_COLOR)
            cell.set_text_props(color=TEXT_COLOR, fontweight="bold")
        else:  # Alternating rows
            cell.set_facecolor("#252525" if i % 2 == 0 else "#2d2d2d")
            cell.set_text_props(color=TEXT_COLOR, fontweight="bold")


def _highlight_fastest_sectors(
    table: Any, data: list[list[Any]], fastest_splits: list[float]
) -> None:
    """Highlight cells with the fastest sector times.
    
    Args:
        table: Matplotlib table object.
        data: Formatted lap time data.
        fastest_splits: List of fastest sector times.
    """
    for col_idx in range(3, 6):  # Sector columns
        for row_idx in range(1, len(data) + 1):
            cell = table[row_idx, col_idx]
            try:
                cell_val = float(cell.get_text().get_text())
                if cell_val == fastest_splits[col_idx - 3]:
                    cell.set_facecolor(FASTEST_SECTOR_COLOR)
                    cell.set_text_props(color=TEXT_COLOR, fontweight="bold")
            except (ValueError, TypeError):
                pass
