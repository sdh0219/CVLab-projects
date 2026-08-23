-- A 线损毁结果 PostGIS 建表脚本
-- 用法: psql -h localhost -U postgres -d <你的库名> -f gis/schema.sql

CREATE EXTENSION IF NOT EXISTS postgis;

DROP TABLE IF EXISTS damage_buildings;
CREATE TABLE damage_buildings (
    id          serial PRIMARY KEY,
    uid         text,
    disaster    text,
    pred_cls    integer,            -- 预测损毁等级 0~4
    pred_label  text,
    true_cls    integer,            -- 真值损毁等级 0~4(来自标注 subtype)
    true_label  text,
    area_m2     double precision,   -- 建筑底面积(原生像素×GSD²)
    geom        geometry(Polygon, 4326)
);

CREATE INDEX idx_damage_geom ON damage_buildings USING GIST (geom);
CREATE INDEX idx_damage_pred ON damage_buildings (pred_cls);
CREATE INDEX idx_damage_disaster ON damage_buildings (disaster);
