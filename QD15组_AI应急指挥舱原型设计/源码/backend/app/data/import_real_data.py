"""Import public real-data package into the local demo database.

The imported records are intentionally conservative:
- public map locations are real OpenStreetMap points;
- non-public quantities such as staff count, inventory and shelter occupancy
  are kept as 0 instead of being fabricated.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.models import models


PROJECT_ROOT = Path(__file__).resolve().parents[3]
# 项目已按四分类重构：真实数据位于项目根目录的"数据集/processed/"
DATA_DIR = PROJECT_ROOT.parent / "数据集" / "processed"


def read_json(name: str) -> list[dict]:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def enum_value(enum_cls, value: str, fallback):
    try:
        return enum_cls(value)
    except Exception:
        return fallback


def reset_tables(db) -> None:
    for table in [
        models.MaterialAllocation,
        models.TransferRecord,
        models.AIDecision,
        models.DisasterEvent,
        models.RescueTeam,
        models.ReliefMaterial,
        models.Shelter,
        models.PopulationData,
        models.RoadStatus,
        models.WeatherData,
    ]:
        db.query(table).delete()
    db.commit()

    # SQLite resets autoincrement through sqlite_sequence when present.
    try:
        for table_name in [
            "material_allocations",
            "transfer_records",
            "ai_decisions",
            "disaster_events",
            "rescue_teams",
            "relief_materials",
            "shelters",
            "population_data",
            "road_status",
            "weather_data",
        ]:
            db.execute(text("DELETE FROM sqlite_sequence WHERE name=:name"), {"name": table_name})
        db.commit()
    except Exception:
        db.rollback()


def import_disasters(db) -> None:
    for row in read_json("real_disaster_events.json"):
        db.add(
            models.DisasterEvent(
                event_name=row["event_name"],
                disaster_type=enum_value(
                    models.DisasterType,
                    row.get("disaster_type", "extreme_weather"),
                    models.DisasterType.extreme_weather,
                ),
                warning_level=enum_value(
                    models.WarningLevel,
                    row.get("warning_level", "yellow"),
                    models.WarningLevel.yellow,
                ),
                response_level=enum_value(
                    models.ResponseLevel,
                    row.get("response_level", "IV"),
                    models.ResponseLevel.level_4,
                ),
                latitude=row["latitude"],
                longitude=row["longitude"],
                affected_area=row.get("affected_area", 0),
                affected_population=row.get("affected_population", 0),
                casualties=row.get("casualties", 0),
                description=(
                    f"{row.get('description', '')}\n"
                    f"数据来源：{row.get('source', '')}；备注：{row.get('note', '')}"
                ).strip(),
            )
        )


def import_rescue(db) -> None:
    rows = read_json("real_rescue_fire_stations.json") + read_json("real_rescue_hospitals.json")
    for row in rows:
        db.add(
            models.RescueTeam(
                team_name=row["name"],
                team_type=row["type"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                member_count=0,
                equipment={
                    "source": row.get("source"),
                    "osm_id": row.get("osm_id"),
                    "note": row.get("note"),
                },
                status="available",
            )
        )


def import_materials(db) -> None:
    for row in read_json("real_material_catalog.json"):
        db.add(
            models.ReliefMaterial(
                material_name=row["material_name"],
                material_type=row["material_type"],
                total_stock=row.get("total_stock", 0),
                allocated=row.get("allocated", 0),
                available=row.get("available", 0),
                unit=row.get("unit", "个"),
                warehouse_name=row.get("warehouse_name"),
                warehouse_latitude=None,
                warehouse_longitude=None,
            )
        )


def import_shelters(db) -> None:
    for row in read_json("real_shelter_candidates.json"):
        db.add(
            models.Shelter(
                shelter_name=row["name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                address=row.get("address") or row.get("facility_type"),
                max_capacity=row.get("max_capacity", 0),
                current_occupancy=row.get("current_occupancy", 0),
                facilities={
                    "facility_type": row.get("facility_type"),
                    "source": row.get("source"),
                    "osm_id": row.get("osm_id"),
                    "note": row.get("note"),
                },
                status="open",
            )
        )


def import_roads(db) -> None:
    for row in read_json("real_major_roads.json"):
        lat = row["latitude"]
        lon = row["longitude"]
        db.add(
            models.RoadStatus(
                road_name=row["name"],
                start_latitude=lat,
                start_longitude=lon,
                end_latitude=lat,
                end_longitude=lon,
                status=row.get("status", "normal"),
                congestion_index=row.get("congestion_index", 0),
            )
        )


def import_weather(db) -> None:
    for row in read_json("real_weather_current.json"):
        rainfall = row.get("rainfall") or 0
        if rainfall >= 100:
            level = models.WarningLevel.red
        elif rainfall >= 50:
            level = models.WarningLevel.orange
        elif rainfall >= 25:
            level = models.WarningLevel.yellow
        elif rainfall > 0:
            level = models.WarningLevel.blue
        else:
            level = models.WarningLevel.blue

        db.add(
            models.WeatherData(
                region_name=row["region_name"],
                rainfall=rainfall,
                wind_speed=row.get("wind_speed"),
                temperature=row.get("temperature"),
                humidity=row.get("humidity"),
                warning_level=level,
                warning_description=(
                    f"Open-Meteo当前气象：降水{rainfall}mm，"
                    f"风速{row.get('wind_speed')}km/h，"
                    f"温度{row.get('temperature')}℃，"
                    f"湿度{row.get('humidity')}%。"
                ),
            )
        )


def import_population(db) -> None:
    # Public package does not include real-time affected population.
    db.add(
        models.PopulationData(
            region_name="成都市中心城区",
            latitude=30.5728,
            longitude=104.0668,
            total_population=None,
            affected_population=0,
            key_population={
                "note": "未接入公开实时人口与受灾人口数据，不编造数值。"
            },
        )
    )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        reset_tables(db)
        import_disasters(db)
        import_rescue(db)
        import_materials(db)
        import_shelters(db)
        import_roads(db)
        import_weather(db)
        import_population(db)
        db.commit()
        print("真实公开数据导入完成")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

