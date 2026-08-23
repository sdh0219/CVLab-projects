# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

from .utils import ensure_dir


def save_fig(path: Path):
    ensure_dir(path.parent)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def plot_weather(weather: pd.DataFrame, fig_dir: Path):
    if weather.empty or "date" not in weather.columns or "precipitation" not in weather.columns:
        return
    df = weather.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return
    monthly = df.groupby(df["date"].dt.to_period("M"))["precipitation"].mean().reset_index()
    monthly["month"] = monthly["date"].astype(str)
    plt.figure(figsize=(10, 4.8))
    plt.plot(monthly["month"], monthly["precipitation"], marker="o", linewidth=1)
    plt.xticks(rotation=60, ha="right")
    plt.xlabel("Month")
    plt.ylabel("Average daily precipitation")
    plt.title("NOAA Weather: Monthly Average Daily Precipitation")
    save_fig(fig_dir / "weather_monthly_precipitation.png")


def plot_earthquake(earthquake: pd.DataFrame, fig_dir: Path):
    if earthquake.empty or "mag" not in earthquake.columns:
        return
    vals = pd.to_numeric(earthquake["mag"], errors="coerce").dropna()
    if vals.empty:
        return
    plt.figure(figsize=(8, 4.8))
    plt.hist(vals, bins=20)
    plt.xlabel("Magnitude")
    plt.ylabel("Event count")
    plt.title("USGS Earthquake Magnitude Distribution")
    save_fig(fig_dir / "earthquake_magnitude_histogram.png")


def plot_resources(resources: pd.DataFrame, fig_dir: Path):
    if resources.empty or "resource_type" not in resources.columns:
        return
    counts = resources["resource_type"].fillna("unknown").astype(str).value_counts()
    plt.figure(figsize=(8, 4.8))
    counts.plot(kind="bar")
    plt.xlabel("Resource type")
    plt.ylabel("Count")
    plt.title("Emergency Resource Counts")
    save_fig(fig_dir / "resource_type_counts.png")


def plot_hazard(unified_hazard: pd.DataFrame, fig_dir: Path):
    if unified_hazard.empty or "hazard_type" not in unified_hazard.columns:
        return
    counts = unified_hazard["hazard_type"].fillna("unknown").astype(str).value_counts().head(15)
    plt.figure(figsize=(9, 4.8))
    counts.plot(kind="bar")
    plt.xlabel("Hazard type")
    plt.ylabel("Event count")
    plt.title("Unified Hazard Event Counts")
    save_fig(fig_dir / "hazard_event_counts.png")


def plot_source_records(fusion_summary: pd.DataFrame, fig_dir: Path):
    if fusion_summary.empty or "dataset" not in fusion_summary.columns:
        return
    df = fusion_summary.copy()
    df["records"] = pd.to_numeric(df["records"], errors="coerce").fillna(0)
    plt.figure(figsize=(10, 5.2))
    plt.bar(df["dataset"], df["records"])
    plt.xticks(rotation=60, ha="right")
    plt.xlabel("Dataset")
    plt.ylabel("Records")
    plt.title("Records by Processed Dataset")
    save_fig(fig_dir / "data_source_records.png")


def make_all_figures(weather, earthquake, resources, unified_hazard, fusion_summary, out_dir: Path):
    fig_dir = out_dir / "figures"
    ensure_dir(fig_dir)
    plot_weather(weather, fig_dir)
    plot_earthquake(earthquake, fig_dir)
    plot_resources(resources, fig_dir)
    plot_hazard(unified_hazard, fig_dir)
    plot_source_records(fusion_summary, fig_dir)
