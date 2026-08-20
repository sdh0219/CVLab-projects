# 真实数据包来源说明

生成时间：2026-06-16

## 数据原则

本数据包仅使用可公开核验的数据源。对公开渠道无法获得的字段，例如实时应急物资库存、救援队伍实际人数、避难场所当前入住人数、实时道路拥堵或封控状态，不进行编造，统一以 `0`、空值或备注说明处理。

## 数据来源

1. OpenStreetMap / Overpass API
   - 用途：医院/诊所点位、消防站点位、道路名称与中心点、学校/体育场馆/社区中心等候选安置点。
   - 许可：OpenStreetMap data is available under the Open Database License.
   - 链接：https://www.openstreetmap.org/copyright
   - API：https://overpass-api.de/

2. Open-Meteo Forecast API
   - 用途：成都市中心坐标当前气象数据，包括气温、相对湿度、降水、风速等。
   - 链接：https://open-meteo.com/

3. 公开气象/新闻信息汇总
   - 用途：真实历史/公开灾情事件描述。
   - 说明：公开网页常给出天气过程、预警、积水、排涝等事实，但不一定给出统一受灾人口、受灾面积和伤亡人数，因此数据库中相关数值不硬编。
   - 复盘案例：1981年成都平原严重洪涝、2020年四川强降雨与流域性洪水、2023年前后四川盆地多轮强降雨、成都城市内涝防治能力提升等公开资料被整理为历史案例和治理改进记录。

4. 公开政策与新闻指标
   - 用途：补充可公开核验的避难场所规模和生活物资保供指标。
   - 人民网四川频道：成都已建成应急避难场所2300余个。
     https://sc.people.com.cn/BIG5/n2/2024/0513/c345167-40841412.html
   - 四川在线：成都市2000余个应急避难场所中，100余个位于城市各个公园里。
     https://sichuan.scol.com.cn/ggxw/202203/58471261.html
   - 新浪四川转载公开报道：粮食、食用油等政府储备满足15日以上市场供应量，猪肉储备不低于城镇常住人口3天消费量。
     https://sc.sina.cn/news/b/2022-05-20/detail-imcwiwst8342255.d.html

## 文件结构

- `osm_*.json`：原始抓取数据。
- `open_meteo_chengdu_current.json`：Open-Meteo 原始气象响应。
- `processed/*.json`：项目可导入的清洗后数据。
- `processed/*.csv`：同内容 CSV 版本，便于查看和汇报。
- `processed/real_disaster_events.*`：公开历史灾害、极端天气与治理改进复盘事件。
- `processed/real_public_policy_indicators.*`：公开报道中的避难场所和生活物资保供指标。
- `processed/manifest.json`：数据包摘要。
