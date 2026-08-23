# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import pandas as pd

from .utils import ensure_dir, save_csv
from .processors import (
    process_weather,
    process_fema,
    process_earthquake,
    process_svi,
    process_resources,
    process_landslide,
    process_roads,
)
from .fusion import build_unified_tables
from .visualization import make_all_figures


def run_pipeline(data_dir: Path, output_dir: Path):
    ensure_dir(output_dir)
    ensure_dir(output_dir / "processed")
    ensure_dir(output_dir / "geojson")
    ensure_dir(output_dir / "figures")

    print("=" * 80)
    print("Project 01 Data Island Fusion Pipeline")
    print(f"Data directory:   {data_dir}")
    print(f"Output directory: {output_dir}")
    print("=" * 80)

    status = []

    weather, s = process_weather(data_dir, output_dir)
    status.append(s)
    print(f"[weather] records={len(weather)} source={s['source_kind']}")

    fema, s = process_fema(data_dir, output_dir)
    status.append(s)
    print(f"[fema] records={len(fema)} source={s['source_kind']}")

    earthquake, s = process_earthquake(data_dir, output_dir)
    status.append(s)
    print(f"[earthquake] records={len(earthquake)} source={s['source_kind']}")

    svi, s = process_svi(data_dir, output_dir)
    status.append(s)
    print(f"[svi] records={len(svi)} source={s['source_kind']}")

    resources, s = process_resources(data_dir, output_dir)
    status.append(s)
    print(f"[resources] records={len(resources)} source={s['source_kind']}")

    landslide, s = process_landslide(data_dir, output_dir)
    status.append(s)
    print(f"[landslide] records={len(landslide)} source={s['source_kind']}")

    roads_summary, s = process_roads(data_dir, output_dir)
    status.append(s)
    print(f"[roads] summary_rows={len(roads_summary)} source={s['source_kind']}")

    status_df = pd.DataFrame(status)
    save_csv(status_df, output_dir / "processed" / "data_source_status.csv")

    fused = build_unified_tables(
        weather=weather,
        fema=fema,
        earthquake=earthquake,
        svi=svi,
        resources=resources,
        landslide=landslide,
        roads_summary=roads_summary,
        out_dir=output_dir,
    )

    make_all_figures(
        weather=weather,
        earthquake=earthquake,
        resources=resources,
        unified_hazard=fused["unified_hazard"],
        fusion_summary=fused["fusion_summary"],
        out_dir=output_dir,
    )

    print("-" * 80)
    print("Finished. Main output files:")
    for p in sorted((output_dir / "processed").glob("*")):
        print(" -", p)
    print("Figures:")
    for p in sorted((output_dir / "figures").glob("*.png")):
        print(" -", p)
    print("-" * 80)
