# -*- coding: utf-8 -*-
"""
把 damage_buildings.geojson 入库到 PostGIS。
依赖: pip install psycopg2-binary shapely
用法:
  python gis/postgis_load.py --dbname gis --user postgres --password 123456 --host localhost

也可直接用 ogr2ogr(若装了 GDAL，更省事)：
  psql ... -f gis/schema.sql        # 先建表
  ogr2ogr -f PostgreSQL "PG:host=localhost dbname=gis user=postgres password=123456" \
      outputs/gis/damage_buildings.geojson -nln damage_buildings -append -nlt POLYGON
"""
import os, sys, json, argparse
from shapely.geometry import shape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C

GEOJSON = os.path.join(C.ROOT, "outputs", "gis", "damage_buildings.geojson")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dbname", required=True)
    ap.add_argument("--user", default="postgres")
    ap.add_argument("--password", default="")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", default="5432")
    ap.add_argument("--geojson", default=GEOJSON)
    ap.add_argument("--create", action="store_true", help="入库前先建表(等价于跑 schema.sql)")
    args = ap.parse_args()

    import psycopg2
    conn = psycopg2.connect(dbname=args.dbname, user=args.user, password=args.password,
                            host=args.host, port=args.port)
    cur = conn.cursor()

    if args.create:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.execute("DROP TABLE IF EXISTS damage_buildings;")
        cur.execute("""
            CREATE TABLE damage_buildings (
                id serial PRIMARY KEY, uid text, disaster text,
                pred_cls integer, pred_label text,
                true_cls integer, true_label text,
                area_m2 double precision,
                geom geometry(Polygon,4326));
            CREATE INDEX idx_damage_geom ON damage_buildings USING GIST(geom);
        """)
        conn.commit()

    with open(args.geojson, encoding="utf-8") as f:
        fc = json.load(f)

    sql = """INSERT INTO damage_buildings
        (uid,disaster,pred_cls,pred_label,true_cls,true_label,area_m2,geom)
        VALUES (%s,%s,%s,%s,%s,%s,%s, ST_GeomFromText(%s,4326))"""
    n = 0
    for ft in fc["features"]:
        p = ft["properties"]
        geom_wkt = shape(ft["geometry"]).wkt
        cur.execute(sql, (p["uid"], p["disaster"], p["pred_cls"], p["pred_label"],
                          p["true_cls"], p["true_label"], p["area_m2"], geom_wkt))
        n += 1
        if n % 2000 == 0:
            conn.commit()
    conn.commit()
    cur.close(); conn.close()
    print(f"已入库 {n} 栋建筑到表 damage_buildings")


if __name__ == "__main__":
    main()
