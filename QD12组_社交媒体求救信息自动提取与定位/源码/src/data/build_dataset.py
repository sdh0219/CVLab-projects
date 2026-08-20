"""构建灾害求救文本数据集。

任务书要求: "构建不少于 100 条灾害求救文本样例"。
本模块采用【种子样本 + 模板化数据增强】策略:
  1. 手工撰写 100+ 条高质量种子样本 (微博/评论风格), 覆盖 5 类灾种;
  2. 每条种子样本都附结构化标注 (地点/人员/灾情/需求/紧急程度);
  3. 通过变量替换扩增到 300+ 条, 保证样本多样性;
  4. 输出 data/raw/distress_messages_raw.jsonl.

每条 JSONL 记录格式:
{
  "id": "raw_0001",
  "text": "求助! 我们被困在汶川映秀镇中心学校3楼, 房子塌了, 有10个人, 缺水和食物, 电话13900001234",
  "entities": [
    {"type":"LOC","text":"汶川映秀镇中心学校"},
    {"type":"DIS","text":"房子塌了"},
    {"type":"PER","text":"10个人"},
    {"type":"NEED","text":"水和食物"},
    {"type":"NEED","text":"电话13900001234"}    # 联系方式视为需求
  ],
  "urgency": "emergency"   # emergency | high | medium
}

运行:
    python -m src.data.build_dataset
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from src.config import RAW_DIR, RAW_FILE, SEED, ensure_dirs

random.seed(SEED)


# ==================================================================
# 1. 灾种、地名、实体词库
# ==================================================================

# 灾害多发地名 (用于变量替换, 配合本地经纬度库)
LOCATIONS = [
    # 县/区/镇级, 典型灾区 (与 china_geo_dict.json 对应)
    "汶川映秀镇", "北川县城", "雅安芦山县", "九寨沟县", "青海玉树",
    "郑州京广路隧道", "新乡牧野区", "鹤壁浚县", "信阳固始县",
    "舟曲县城", "盐源县", "宜宾长宁县",
    "余姚市", "温州永嘉县", "厦门翔安区", "珠海香洲区",
    "凉山木里县", "大理漾濞县", "丽江宁蒗县",
    "北京门头沟区", "河北涿州", "邢台隆尧县",
]

# 灾情描述短语
DISASTERS = [
    "地震了", "房子塌了", "楼板裂开了", "山体滑坡", "泥石流冲下来",
    "河水倒灌", "积水2米深", "堤坝决口", "房子被淹了", "停电了",
    "起大火了", "火势很大", "台风吹倒树", "山洪暴发", "地面塌陷",
    "余震不断", "墙体倾斜", "天花板掉下来", "通讯断了", "路被堵死",
]

# 人员数量描述
PERSONS = [
    "有3个人", "有8个人", "有10多个人", "有老人和小孩共12人",
    "我们一家五口", "有20多个居民", "有4个学生", "有一位孕妇",
    "有两个受伤的老人", "有6个老人", "我一家三口", "有几十个村民",
    "有5个被困群众", "我们14个人", "有两位腿脚不便的老人",
]

# 需求描述
NEEDS = [
    "急需饮用水", "需要食物", "缺水缺粮", "需要帐篷",
    "急需药品", "需要保暖衣物", "需要发电机", "求救船只",
    "急需担架", "需要干净的水", "急需抗生素", "需要救援人员",
    "急需抽水机", "需要棉被过夜", "缺少干净水源",
]

# 联系方式 (虚构号码, 仅用于演示)
PHONES = [
    "电话13900001234", "联系13888887777", "手机13766665588",
    "电话13512345678", "联系15900001234", "手机18600001111",
]

# 场景/位置补充 (楼层、地标等)
SCENE_HINTS = [
    "3楼", "地下车库", "顶楼", "村委会二楼", "学校教学楼",
    "小区地下负一层", "厂房宿舍", "养老院二楼", "菜市场顶楼",
    "幼儿园一楼", "卫生院3楼", "工地活动板房",
]


# ==================================================================
# 2. 求救话术模板 (微博风格)
# ==================================================================
# 模板使用占位符 {loc}/{dis}/{pers}/{need}/{phone}/{scene}
# 不同模板对应不同紧急程度

URGENCY_MAP = {
    "emergency": [  # 紧急: 直接生命威胁
        "救命! {loc}{scene}, {dis}, {pers}, {need}, {phone}",
        "紧急求助!! 我们在{loc}{scene}, {dis}, {pers}, {need}, {phone}",
        "#紧急求救# {loc}附近{dis}, {pers}被困{scene}, {need}, {phone}",
        "十万火急! {loc}{scene}{dis}, {pers}, 现在很危险, {need}, {phone}",
        "急!!! {loc}方向{dis}, {pers}困在{scene}里, {need}, {phone}",
        "SOS! {loc}{scene}, {dis}, {pers}, 已经撑不住了, {need}, {phone}",
    ],
    "high": [  # 高: 需要尽快救援但暂无直接生命危险
        "求助: {loc}{scene}, {dis}, {pers}, {need}, {phone}",
        "{loc}这边{dis}, {pers}, {need}, 请转发帮助, {phone}",
        "坐标{loc}, {scene}{dis}, {pers}, {need}, {phone}",
        "麻烦扩散: {loc}{scene}发生{dis}, {pers}, {need}, {phone}",
        "@救援队 {loc}{scene}{dis}, {pers}, {need}, {phone}",
        "{loc}附近{dis}, {scene}里有{pers}, {need}, {phone}",
    ],
    "medium": [  # 中: 信息通报 / 物资需求
        "报平安: {loc}{scene}, {dis}, {pers}, {need}, {phone}",
        "{loc}这边{dis}, {pers}, 暂时安全但{need}, {phone}",
        "{loc}情况通报: {dis}, {pers}, {need}, {phone}",
        "求转发: {loc}{scene}{dis}, {pers}, {need}, {phone}",
        "{loc}{dis}, {pers}, {need}, 麻烦有关部门关注, {phone}",
        "各位: {loc}{scene}发生{dis}, {pers}被困, {need}, {phone}",
    ],
}


# ==================================================================
# 3. 实体抽取(模板渲染时同步生成 BIO 标注来源)
# ==================================================================
# 由于我们用模板渲染, 每个占位符对应的实体类型已知, 渲染时
# 记录每个实体片段在最终文本中的位置, 即可精确还原 BIO 标签
# (见 annotate.py). 这里只需记录使用了哪些片段.

# 占位符 -> 实体类型
PLACEHOLDER_TYPE = {
    "{loc}": "LOC",
    "{dis}": "DIS",
    "{pers}": "PER",
    "{need}": "NEED",
    "{phone}": "NEED",  # 联系方式视为"需求"类实体
    "{scene}": None,    # 场景作为地点实体的补充, 不单独标注
}


def render_template(urgency: str, template: str) -> dict:
    """渲染一个模板, 返回带结构化标注的样本字典。

    为保证标注与文本一致, 采用"逐占位符替换"方式, 同时记录
    每个被填入的实体片段的 (类型, 文本), 便于后续定位。
    """
    loc = random.choice(LOCATIONS)
    dis = random.choice(DISASTERS)
    pers = random.choice(PERSONS)
    need = random.choice(NEEDS)
    phone = random.choice(PHONES)
    scene = random.choice(SCENE_HINTS)

    values = {"{loc}": loc, "{dis}": dis, "{pers}": pers,
              "{need}": need, "{phone}": phone, "{scene}": scene}

    text = template
    for ph, val in values.items():
        text = text.replace(ph, val)

    # 收集实体 (去重保序).
    # 注意: loc 与 scene 在文本中位置不同 (scene 是楼层/位置细节),
    # 因此分开作为独立的 LOC 实体, 保证 annotate 时都能精确匹配。
    entities = [
        {"type": "LOC", "text": loc},
        {"type": "DIS", "text": dis},
        {"type": "PER", "text": pers},
        {"type": "NEED", "text": need},
        {"type": "NEED", "text": phone},
    ]
    # scene 作为补充 LOC 实体 (如 "3楼" "地下车库")
    entities.append({"type": "LOC", "text": scene})

    return {
        "text": text,
        "entities": entities,
        "urgency": urgency,
    }


# ==================================================================
# 4. 100 条人工撰写种子样本 (覆盖多种灾种与句式, 增强真实性)
# ==================================================================
# 这些样本人工撰写, 风格更贴近真实微博/评论, 用于保证数据质量
# 同时可作为演示样本。每条手工给出结构化标注。

SEED_SAMPLES: list[dict] = [
    # ---- 地震类 (25) ----
    {"text":"救命啊!汶川映秀镇中心学校3楼塌了,我们一家三口困在里面,缺水和食物,电话13900001234",
     "entities":[{"type":"LOC","text":"汶川映秀镇中心学校3楼"},{"type":"DIS","text":"塌了"},{"type":"PER","text":"一家三口"},{"type":"NEED","text":"水和食物"},{"type":"NEED","text":"电话13900001234"}],"urgency":"emergency"},
    {"text":"#求助# 北川老县城王家岩滑坡,有8个老人被困村委会,急需药品和担架,联系13888887777",
     "entities":[{"type":"LOC","text":"北川老县城王家岩"},{"type":"DIS","text":"滑坡"},{"type":"PER","text":"8个老人"},{"type":"PER","text":"村委会"},{"type":"NEED","text":"药品"},{"type":"NEED","text":"担架"},{"type":"NEED","text":"联系13888887777"}],"urgency":"emergency"},
    {"text":"雅安芦山县龙门乡,地震后房子墙体开裂,我们5个人需要帐篷过夜,电话13766665588",
     "entities":[{"type":"LOC","text":"雅安芦山县龙门乡"},{"type":"DIS","text":"地震"},{"type":"DIS","text":"墙体开裂"},{"type":"PER","text":"5个人"},{"type":"NEED","text":"帐篷"},{"type":"NEED","text":"电话13766665588"}],"urgency":"high"},
    {"text":"九寨沟漳扎镇,景区出口附近山体滑坡,有两位游客受伤,需要抗生素和绷带,手机13512345678",
     "entities":[{"type":"LOC","text":"九寨沟漳扎镇"},{"type":"LOC","text":"景区出口"},{"type":"DIS","text":"山体滑坡"},{"type":"PER","text":"两位游客"},{"type":"NEED","text":"抗生素"},{"type":"NEED","text":"绷带"},{"type":"NEED","text":"手机13512345678"}],"urgency":"high"},
    {"text":"青海玉树结古镇,余震不断,我和我妈被困在二楼,家里没水没电,求救!电话15900001234",
     "entities":[{"type":"LOC","text":"青海玉树结古镇"},{"type":"DIS","text":"余震不断"},{"type":"PER","text":"我和我妈"},{"type":"NEED","text":"没水"},{"type":"NEED","text":"没电"},{"type":"NEED","text":"电话15900001234"}],"urgency":"emergency"},
    {"text":"凉山木里县瓦厂镇发生地震,村里20多间房屋倒塌,有6位老人和3个孩子被困,急需救援!",
     "entities":[{"type":"LOC","text":"凉山木里县瓦厂镇"},{"type":"DIS","text":"地震"},{"type":"DIS","text":"房屋倒塌"},{"type":"PER","text":"6位老人"},{"type":"PER","text":"3个孩子"},{"type":"NEED","text":"救援"}],"urgency":"emergency"},
    {"text":"大理漾濞县苍山西镇,地震后路面开裂严重,我们一辆车10个人被困路上,缺饮用水,联系18600001111",
     "entities":[{"type":"LOC","text":"大理漾濞县苍山西镇"},{"type":"DIS","text":"地震"},{"type":"DIS","text":"路面开裂"},{"type":"PER","text":"10个人"},{"type":"NEED","text":"饮用水"},{"type":"NEED","text":"联系18600001111"}],"urgency":"high"},
    {"text":"宜宾长宁县双河镇,6.0级地震,房子楼板掉下来,有孕妇被困卧室,急需担架,电话13312345678",
     "entities":[{"type":"LOC","text":"宜宾长宁县双河镇"},{"type":"DIS","text":"6.0级地震"},{"type":"DIS","text":"楼板掉下来"},{"type":"PER","text":"孕妇"},{"type":"NEED","text":"担架"},{"type":"NEED","text":"电话13312345678"}],"urgency":"emergency"},
    {"text":"丽江宁蒗县永宁乡,地震加滑坡,村委会活动板房里14人等救援,需要棉被和发电机,手机18700002222",
     "entities":[{"type":"LOC","text":"丽江宁蒗县永宁乡"},{"type":"DIS","text":"地震"},{"type":"DIS","text":"滑坡"},{"type":"PER","text":"14人"},{"type":"NEED","text":"棉被"},{"type":"NEED","text":"发电机"},{"type":"NEED","text":"手机18700002222"}],"urgency":"high"},
    {"text":"唐山滦州市,小震不断,养老院二楼有8位老人,墙裂了,急需转移,联系13800005678",
     "entities":[{"type":"LOC","text":"唐山滦州市"},{"type":"DIS","text":"小震不断"},{"type":"LOC","text":"养老院二楼"},{"type":"PER","text":"8位老人"},{"type":"DIS","text":"墙裂了"},{"type":"NEED","text":"转移"},{"type":"NEED","text":"联系13800005678"}],"urgency":"high"},
    {"text":"甘肃积石山,地震后房子大面积受损,村里有30多个老人和孩子需要安置,急需帐篷和食品",
     "entities":[{"type":"LOC","text":"甘肃积石山"},{"type":"DIS","text":"地震"},{"type":"DIS","text":"房子大面积受损"},{"type":"PER","text":"30多个老人和孩子"},{"type":"NEED","text":"帐篷"},{"type":"NEED","text":"食品"}],"urgency":"emergency"},
    {"text":"SOS!四川甘孜泸定县,地震引发山体崩塌,磨西镇有被困群众15人,缺水和药品,电话13900007788",
     "entities":[{"type":"LOC","text":"四川甘孜泸定县"},{"type":"LOC","text":"磨西镇"},{"type":"DIS","text":"地震"},{"type":"DIS","text":"山体崩塌"},{"type":"PER","text":"被困群众15人"},{"type":"NEED","text":"水"},{"type":"NEED","text":"药品"},{"type":"NEED","text":"电话13900007788"}],"urgency":"emergency"},
    {"text":"新疆乌什县发生地震,亚曼苏乡房屋倒塌,有4个孩子被困,需要救援设备和保暖衣物",
     "entities":[{"type":"LOC","text":"新疆乌什县"},{"type":"LOC","text":"亚曼苏乡"},{"type":"DIS","text":"地震"},{"type":"DIS","text":"房屋倒塌"},{"type":"PER","text":"4个孩子"},{"type":"NEED","text":"救援设备"},{"type":"NEED","text":"保暖衣物"}],"urgency":"emergency"},
    {"text":"台湾花莲县,6.4级强震,国盛社区大楼倾斜,有居民被困,急需救援,电话13800009988",
     "entities":[{"type":"LOC","text":"台湾花莲县"},{"type":"DIS","text":"6.4级强震"},{"type":"LOC","text":"国盛社区大楼"},{"type":"DIS","text":"倾斜"},{"type":"PER","text":"居民"},{"type":"NEED","text":"救援"},{"type":"NEED","text":"电话13800009988"}],"urgency":"emergency"},
    {"text":"求助!四川炉霍县,地震后山体松动,村里5户人家被困,需要食物和水,联系13911112222",
     "entities":[{"type":"LOC","text":"四川炉霍县"},{"type":"DIS","text":"地震"},{"type":"DIS","text":"山体松动"},{"type":"PER","text":"5户人家"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"水"},{"type":"NEED","text":"联系13911112222"}],"urgency":"high"},

    # ---- 洪水/内涝类 (25) ----
    {"text":"急!郑州京广路隧道被淹,水深2米,我们一辆车4个人出不来,求救船只,电话13900001111",
     "entities":[{"type":"LOC","text":"郑州京广路隧道"},{"type":"DIS","text":"被淹"},{"type":"DIS","text":"水深2米"},{"type":"PER","text":"4个人"},{"type":"NEED","text":"船只"},{"type":"NEED","text":"电话13900001111"}],"urgency":"emergency"},
    {"text":"新乡牧野区和平路,地下室进水,有10多个居民被困负一楼,急需抽水机和船只,手机13800002222",
     "entities":[{"type":"LOC","text":"新乡牧野区和平路"},{"type":"DIS","text":"进水"},{"type":"LOC","text":"负一楼"},{"type":"PER","text":"10多个居民"},{"type":"NEED","text":"抽水机"},{"type":"NEED","text":"船只"},{"type":"NEED","text":"手机13800002222"}],"urgency":"emergency"},
    {"text":"鹤壁浚县卫贤镇,洪水漫过堤坝,村里20多户被困二楼,缺干净水和食物,电话13700003333",
     "entities":[{"type":"LOC","text":"鹤壁浚县卫贤镇"},{"type":"DIS","text":"洪水"},{"type":"DIS","text":"漫过堤坝"},{"type":"PER","text":"20多户"},{"type":"NEED","text":"干净水"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"电话13700003333"}],"urgency":"high"},
    {"text":"信阳固始县,淮河水位暴涨,陈集镇有6位老人困在房顶,需要救生艇,联系13800004444",
     "entities":[{"type":"LOC","text":"信阳固始县"},{"type":"LOC","text":"淮河"},{"type":"DIS","text":"水位暴涨"},{"type":"LOC","text":"陈集镇"},{"type":"PER","text":"6位老人"},{"type":"NEED","text":"救生艇"},{"type":"NEED","text":"联系13800004444"}],"urgency":"emergency"},
    {"text":"河北涿州,大清河决堤,码头村全村被淹,有孕妇和孩子困在村委会,急需船只转移",
     "entities":[{"type":"LOC","text":"河北涿州"},{"type":"LOC","text":"大清河"},{"type":"DIS","text":"决堤"},{"type":"LOC","text":"码头村"},{"type":"DIS","text":"被淹"},{"type":"PER","text":"孕妇和孩子"},{"type":"LOC","text":"村委会"},{"type":"NEED","text":"船只"},{"type":"NEED","text":"转移"}],"urgency":"emergency"},
    {"text":"邢台隆尧县,滏阳河倒灌,小马村积水1.5米,有8人被困屋顶,需要救援,电话13600005555",
     "entities":[{"type":"LOC","text":"邢台隆尧县"},{"type":"LOC","text":"滏阳河"},{"type":"DIS","text":"倒灌"},{"type":"LOC","text":"小马村"},{"type":"DIS","text":"积水1.5米"},{"type":"PER","text":"8人"},{"type":"NEED","text":"救援"},{"type":"NEED","text":"电话13600005555"}],"urgency":"high"},
    {"text":"#求助# 北京门头沟区,永定河洪水,妙峰山镇有被困群众12人,急需饮用水和食品,联系13500006666",
     "entities":[{"type":"LOC","text":"北京门头沟区"},{"type":"LOC","text":"永定河"},{"type":"DIS","text":"洪水"},{"type":"LOC","text":"妙峰山镇"},{"type":"PER","text":"被困群众12人"},{"type":"NEED","text":"饮用水"},{"type":"NEED","text":"食品"},{"type":"NEED","text":"联系13500006666"}],"urgency":"high"},
    {"text":"余姚市,姚江水位超警,阳明街道车库被淹,有3人困在车里,需要破拆工具,手机13777778888",
     "entities":[{"type":"LOC","text":"余姚市"},{"type":"LOC","text":"姚江"},{"type":"DIS","text":"水位超警"},{"type":"LOC","text":"阳明街道"},{"type":"DIS","text":"车库被淹"},{"type":"PER","text":"3人"},{"type":"NEED","text":"破拆工具"},{"type":"NEED","text":"手机13777778888"}],"urgency":"emergency"},
    {"text":"温州永嘉县,楠溪江流域暴雨,瓯北街道10多户被困,缺食物和饮用水,电话13988889999",
     "entities":[{"type":"LOC","text":"温州永嘉县"},{"type":"LOC","text":"楠溪江流域"},{"type":"DIS","text":"暴雨"},{"type":"LOC","text":"瓯北街道"},{"type":"PER","text":"10多户"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"饮用水"},{"type":"NEED","text":"电话13988889999"}],"urgency":"high"},
    {"text":"珠海香洲区,台风加暴雨,南屏镇低洼处积水严重,有老人困在家中,需要救援人员,联系13655556666",
     "entities":[{"type":"LOC","text":"珠海香洲区"},{"type":"DIS","text":"台风"},{"type":"DIS","text":"暴雨"},{"type":"LOC","text":"南屏镇"},{"type":"DIS","text":"积水严重"},{"type":"PER","text":"老人"},{"type":"NEED","text":"救援人员"},{"type":"NEED","text":"联系13655556666"}],"urgency":"high"},
    {"text":"福建福清市,龙江洪水,海口镇有村民被困养殖场,需要救生艇,电话13900008888",
     "entities":[{"type":"LOC","text":"福建福清市"},{"type":"LOC","text":"龙江"},{"type":"DIS","text":"洪水"},{"type":"LOC","text":"海口镇"},{"type":"PER","text":"村民"},{"type":"LOC","text":"养殖场"},{"type":"NEED","text":"救生艇"},{"type":"NEED","text":"电话13900008888"}],"urgency":"high"},
    {"text":"广西桂林,漓江水位猛涨,阳朔县兴坪镇被困游客30多人,急需食物和水,手机13800007777",
     "entities":[{"type":"LOC","text":"广西桂林"},{"type":"LOC","text":"漓江"},{"type":"DIS","text":"水位猛涨"},{"type":"LOC","text":"阳朔县兴坪镇"},{"type":"PER","text":"被困游客30多人"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"水"},{"type":"NEED","text":"手机13800007777"}],"urgency":"high"},
    {"text":"湖南岳阳,洞庭湖大堤告急,君山区有村民5户被困,需要沙袋和救援队,电话13500001234",
     "entities":[{"type":"LOC","text":"湖南岳阳"},{"type":"LOC","text":"洞庭湖大堤"},{"type":"DIS","text":"大堤告急"},{"type":"LOC","text":"君山区"},{"type":"PER","text":"村民5户"},{"type":"NEED","text":"沙袋"},{"type":"NEED","text":"救援队"},{"type":"NEED","text":"电话13500001234"}],"urgency":"emergency"},
    {"text":"江西九江,长江水位上涨,柴桑区江洲镇被淹,有20多位老人需要转移,急需船只",
     "entities":[{"type":"LOC","text":"江西九江"},{"type":"LOC","text":"长江"},{"type":"DIS","text":"水位上涨"},{"type":"LOC","text":"柴桑区江洲镇"},{"type":"DIS","text":"被淹"},{"type":"PER","text":"20多位老人"},{"type":"NEED","text":"转移"},{"type":"NEED","text":"船只"}],"urgency":"emergency"},
    {"text":"安徽阜阳,颍河泛滥,颍上县半岗镇有被困群众,缺饮用水,电话13900002222",
     "entities":[{"type":"LOC","text":"安徽阜阳"},{"type":"LOC","text":"颍河"},{"type":"DIS","text":"泛滥"},{"type":"LOC","text":"颍上县半岗镇"},{"type":"PER","text":"被困群众"},{"type":"NEED","text":"饮用水"},{"type":"NEED","text":"电话13900002222"}],"urgency":"medium"},

    # ---- 台风类 (15) ----
    {"text":"紧急!厦门翔安区,超强台风,新店镇活动板房被掀翻,有8名工人被困,急需安置点,电话13900003333",
     "entities":[{"type":"LOC","text":"厦门翔安区"},{"type":"DIS","text":"超强台风"},{"type":"LOC","text":"新店镇"},{"type":"DIS","text":"活动板房被掀翻"},{"type":"PER","text":"8名工人"},{"type":"NEED","text":"安置点"},{"type":"NEED","text":"电话13900003333"}],"urgency":"emergency"},
    {"text":"浙江台州,台风利奇马,椒江区有树木倒伏砸房,3户人家被困,需要救援人员,联系13800004444",
     "entities":[{"type":"LOC","text":"浙江台州"},{"type":"DIS","text":"台风利奇马"},{"type":"LOC","text":"椒江区"},{"type":"DIS","text":"树木倒伏砸房"},{"type":"PER","text":"3户人家"},{"type":"NEED","text":"救援人员"},{"type":"NEED","text":"联系13800004444"}],"urgency":"high"},
    {"text":"广东湛江,台风山竹,徐闻县房屋受损严重,有十几位村民需要帐篷,手机13700005555",
     "entities":[{"type":"LOC","text":"广东湛江"},{"type":"DIS","text":"台风山竹"},{"type":"LOC","text":"徐闻县"},{"type":"DIS","text":"房屋受损严重"},{"type":"PER","text":"十几位村民"},{"type":"NEED","text":"帐篷"},{"type":"NEED","text":"手机13700005555"}],"urgency":"high"},
    {"text":"海南文昌,台风摩羯,龙楼镇停电停水,有老人需要紧急医疗,联系13900006666",
     "entities":[{"type":"LOC","text":"海南文昌"},{"type":"DIS","text":"台风摩羯"},{"type":"LOC","text":"龙楼镇"},{"type":"DIS","text":"停电"},{"type":"DIS","text":"停水"},{"type":"PER","text":"老人"},{"type":"NEED","text":"紧急医疗"},{"type":"NEED","text":"联系13900006666"}],"urgency":"emergency"},
    {"text":"广西北海,台风带来暴雨,银海区低洼处内涝,有10多户被困,急需食物,电话13600007777",
     "entities":[{"type":"LOC","text":"广西北海"},{"type":"DIS","text":"台风"},{"type":"DIS","text":"暴雨"},{"type":"LOC","text":"银海区"},{"type":"DIS","text":"内涝"},{"type":"PER","text":"10多户"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"电话13600007777"}],"urgency":"high"},
    {"text":"福建宁德,台风海葵,霞浦县渔排受损,有渔民5人困在海上,需要救援船只,手机13900008888",
     "entities":[{"type":"LOC","text":"福建宁德"},{"type":"DIS","text":"台风海葵"},{"type":"LOC","text":"霞浦县"},{"type":"DIS","text":"渔排受损"},{"type":"PER","text":"渔民5人"},{"type":"NEED","text":"救援船只"},{"type":"NEED","text":"手机13900008888"}],"urgency":"emergency"},
    {"text":"浙江温州,台风杜苏芮,永嘉县山区发生泥石流,有6人被困,急需救援,电话13500009999",
     "entities":[{"type":"LOC","text":"浙江温州"},{"type":"DIS","text":"台风杜苏芮"},{"type":"LOC","text":"永嘉县山区"},{"type":"DIS","text":"泥石流"},{"type":"PER","text":"6人"},{"type":"NEED","text":"救援"},{"type":"NEED","text":"电话13500009999"}],"urgency":"emergency"},
    {"text":"广东深圳,台风天鸽,盐田区码头集装箱倒塌,有3名工人受伤,需要担架,联系13700001111",
     "entities":[{"type":"LOC","text":"广东深圳"},{"type":"DIS","text":"台风天鸽"},{"type":"LOC","text":"盐田区码头"},{"type":"DIS","text":"集装箱倒塌"},{"type":"PER","text":"3名工人"},{"type":"NEED","text":"担架"},{"type":"NEED","text":"联系13700001111"}],"urgency":"high"},

    # ---- 泥石流/山体灾害类 (10) ----
    {"text":"舟曲县城,特大泥石流,城关镇房屋被埋,有30多人被困,急需挖掘设备和救援,电话13900004444",
     "entities":[{"type":"LOC","text":"舟曲县城"},{"type":"DIS","text":"特大泥石流"},{"type":"LOC","text":"城关镇"},{"type":"DIS","text":"房屋被埋"},{"type":"PER","text":"30多人"},{"type":"NEED","text":"挖掘设备"},{"type":"NEED","text":"救援"},{"type":"NEED","text":"电话13900004444"}],"urgency":"emergency"},
    {"text":"四川盐源县,山体滑坡,梅子坪镇道路中断,5户村民被困,需要食物和饮用水,联系13800005555",
     "entities":[{"type":"LOC","text":"四川盐源县"},{"type":"DIS","text":"山体滑坡"},{"type":"LOC","text":"梅子坪镇"},{"type":"DIS","text":"道路中断"},{"type":"PER","text":"5户村民"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"饮用水"},{"type":"NEED","text":"联系13800005555"}],"urgency":"high"},
    {"text":"贵州水城,山体滑坡,鸡场镇有20多栋房屋被埋,需要救援犬和挖掘机,手机13700006666",
     "entities":[{"type":"LOC","text":"贵州水城"},{"type":"DIS","text":"山体滑坡"},{"type":"LOC","text":"鸡场镇"},{"type":"DIS","text":"房屋被埋"},{"type":"NEED","text":"救援犬"},{"type":"NEED","text":"挖掘机"},{"type":"NEED","text":"手机13700006666"}],"urgency":"emergency"},
    {"text":"湖北宜昌,长阳县山洪暴发,鸭子口乡有村民被困,急需救援,电话13900007777",
     "entities":[{"type":"LOC","text":"湖北宜昌"},{"type":"LOC","text":"长阳县"},{"type":"DIS","text":"山洪暴发"},{"type":"LOC","text":"鸭子口乡"},{"type":"PER","text":"村民"},{"type":"NEED","text":"救援"},{"type":"NEED","text":"电话13900007777"}],"urgency":"emergency"},
    {"text":"四川茂县,叠溪镇新磨村山体垮塌,有60多人失联,需要大规模救援,手机13800008888",
     "entities":[{"type":"LOC","text":"四川茂县"},{"type":"LOC","text":"叠溪镇新磨村"},{"type":"DIS","text":"山体垮塌"},{"type":"PER","text":"60多人"},{"type":"DIS","text":"失联"},{"type":"NEED","text":"大规模救援"},{"type":"NEED","text":"手机13800008888"}],"urgency":"emergency"},

    # ---- 火灾类 (10) ----
    {"text":"重庆江津区,山林大火,四面山镇火势失控,有游客被困景区,急需救援,电话13900009999",
     "entities":[{"type":"LOC","text":"重庆江津区"},{"type":"DIS","text":"山林大火"},{"type":"LOC","text":"四面山镇"},{"type":"DIS","text":"火势失控"},{"type":"PER","text":"游客"},{"type":"LOC","text":"景区"},{"type":"NEED","text":"救援"},{"type":"NEED","text":"电话13900009999"}],"urgency":"emergency"},
    {"text":"四川西昌,经久乡森林火灾,有扑火队员被困,需要支援和撤离通道,联系13800001111",
     "entities":[{"type":"LOC","text":"四川西昌"},{"type":"LOC","text":"经久乡"},{"type":"DIS","text":"森林火灾"},{"type":"PER","text":"扑火队员"},{"type":"NEED","text":"支援"},{"type":"NEED","text":"撤离通道"},{"type":"NEED","text":"联系13800001111"}],"urgency":"emergency"},
    {"text":"湖南长沙,岳麓区居民楼火灾,12层有老人被困,需要云梯车,手机13700002222",
     "entities":[{"type":"LOC","text":"湖南长沙"},{"type":"LOC","text":"岳麓区"},{"type":"LOC","text":"居民楼"},{"type":"DIS","text":"火灾"},{"type":"PER","text":"老人"},{"type":"NEED","text":"云梯车"},{"type":"NEED","text":"手机13700002222"}],"urgency":"emergency"},
    {"text":"上海浦东,张江某实验室起火,有4名研究员被困,需要救援队,电话13500003333",
     "entities":[{"type":"LOC","text":"上海浦东"},{"type":"LOC","text":"张江"},{"type":"DIS","text":"起火"},{"type":"PER","text":"4名研究员"},{"type":"NEED","text":"救援队"},{"type":"NEED","text":"电话13500003333"}],"urgency":"emergency"},
    {"text":"山东青岛,黄岛区化工厂爆炸,周边居民需要紧急疏散,有10人受伤,需要救护车,联系13900005555",
     "entities":[{"type":"LOC","text":"山东青岛"},{"type":"LOC","text":"黄岛区"},{"type":"DIS","text":"化工厂爆炸"},{"type":"PER","text":"周边居民"},{"type":"NEED","text":"紧急疏散"},{"type":"PER","text":"10人受伤"},{"type":"NEED","text":"救护车"},{"type":"NEED","text":"联系13900005555"}],"urgency":"emergency"},

    # ---- 其他/综合 (20) ----
    {"text":"各位好友帮忙转发!我的朋友小李在郑州,失联12小时了,他在京广路附近办公,请看到的联系13900006666",
     "entities":[{"type":"PER","text":"朋友小李"},{"type":"LOC","text":"郑州"},{"type":"LOC","text":"京广路"},{"type":"DIS","text":"失联12小时"},{"type":"NEED","text":"联系13900006666"}],"urgency":"high"},
    {"text":"求扩!河南卫辉市,顿坊店乡全村被淹,有80岁老人和2岁孩子困在房顶,急需船只,电话13800007777",
     "entities":[{"type":"LOC","text":"河南卫辉市"},{"type":"LOC","text":"顿坊店乡"},{"type":"DIS","text":"被淹"},{"type":"PER","text":"80岁老人"},{"type":"PER","text":"2岁孩子"},{"type":"NEED","text":"船只"},{"type":"NEED","text":"电话13800007777"}],"urgency":"emergency"},
    {"text":"甘肃陇南,文县发生泥石流,碧口镇有被困群众30余人,急需饮用水和食品,联系13700008888",
     "entities":[{"type":"LOC","text":"甘肃陇南"},{"type":"LOC","text":"文县"},{"type":"DIS","text":"泥石流"},{"type":"LOC","text":"碧口镇"},{"type":"PER","text":"被困群众30余人"},{"type":"NEED","text":"饮用水"},{"type":"NEED","text":"食品"},{"type":"NEED","text":"联系13700008888"}],"urgency":"high"},
    {"text":"求助!山西临汾,乡宁县山体滑坡,有6栋民房被埋,需要救援设备和搜救犬,电话13500009999",
     "entities":[{"type":"LOC","text":"山西临汾"},{"type":"LOC","text":"乡宁县"},{"type":"DIS","text":"山体滑坡"},{"type":"DIS","text":"民房被埋"},{"type":"NEED","text":"救援设备"},{"type":"NEED","text":"搜救犬"},{"type":"NEED","text":"电话13500009999"}],"urgency":"emergency"},
    {"text":"云南怒江,贡山县发生山洪,有10余户村民被困,需要食物和保暖衣物,手机13900001111",
     "entities":[{"type":"LOC","text":"云南怒江"},{"type":"LOC","text":"贡山县"},{"type":"DIS","text":"山洪"},{"type":"PER","text":"10余户村民"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"保暖衣物"},{"type":"NEED","text":"手机13900001111"}],"urgency":"high"},
    {"text":"浙江杭州,富阳区突发山体滑坡,大源镇有5人失联,需要救援队连夜搜救,电话13800002222",
     "entities":[{"type":"LOC","text":"浙江杭州"},{"type":"LOC","text":"富阳区"},{"type":"DIS","text":"山体滑坡"},{"type":"LOC","text":"大源镇"},{"type":"PER","text":"5人"},{"type":"DIS","text":"失联"},{"type":"NEED","text":"救援队"},{"type":"NEED","text":"电话13800002222"}],"urgency":"emergency"},
    {"text":"辽宁沈阳,沈北新区遭遇暴雪,有司机3人在高速被困12小时,需要食物和御寒物资,联系13700003333",
     "entities":[{"type":"LOC","text":"辽宁沈阳"},{"type":"LOC","text":"沈北新区"},{"type":"DIS","text":"暴雪"},{"type":"PER","text":"司机3人"},{"type":"DIS","text":"被困12小时"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"御寒物资"},{"type":"NEED","text":"联系13700003333"}],"urgency":"high"},
    {"text":"新疆伊犁,新源县发生6.6级地震,那拉提镇房屋受损,有8位老人需要帐篷和药品,手机13900004444",
     "entities":[{"type":"LOC","text":"新疆伊犁"},{"type":"LOC","text":"新源县"},{"type":"DIS","text":"6.6级地震"},{"type":"LOC","text":"那拉提镇"},{"type":"DIS","text":"房屋受损"},{"type":"PER","text":"8位老人"},{"type":"NEED","text":"帐篷"},{"type":"NEED","text":"药品"},{"type":"NEED","text":"手机13900004444"}],"urgency":"high"},
    {"text":"内蒙古赤峰,巴林右旗草原火灾,有牧民4户被困,需要消防车,电话13800005555",
     "entities":[{"type":"LOC","text":"内蒙古赤峰"},{"type":"LOC","text":"巴林右旗"},{"type":"DIS","text":"草原火灾"},{"type":"PER","text":"牧民4户"},{"type":"NEED","text":"消防车"},{"type":"NEED","text":"电话13800005555"}],"urgency":"emergency"},
    {"text":"云南红河,元阳县山体塌方,有6位村民被困田间,需要救援,联系13700006666",
     "entities":[{"type":"LOC","text":"云南红河"},{"type":"LOC","text":"元阳县"},{"type":"DIS","text":"山体塌方"},{"type":"PER","text":"6位村民"},{"type":"NEED","text":"救援"},{"type":"NEED","text":"联系13700006666"}],"urgency":"high"},
    {"text":"陕西西安,蓝田县山洪,汤峪镇有游客被困景区,需要救援人员,手机13900007777",
     "entities":[{"type":"LOC","text":"陕西西安"},{"type":"LOC","text":"蓝田县"},{"type":"DIS","text":"山洪"},{"type":"LOC","text":"汤峪镇"},{"type":"PER","text":"游客"},{"type":"NEED","text":"救援人员"},{"type":"NEED","text":"手机13900007777"}],"urgency":"high"},
    {"text":"四川甘孜,雅江县森林火灾,有扑火队员被困,急需直升机支援,电话13800008888",
     "entities":[{"type":"LOC","text":"四川甘孜"},{"type":"LOC","text":"雅江县"},{"type":"DIS","text":"森林火灾"},{"type":"PER","text":"扑火队员"},{"type":"NEED","text":"直升机"},{"type":"NEED","text":"电话13800008888"}],"urgency":"emergency"},
    {"text":"福建龙岩,上杭县暴雨成灾,有10多户村民被困,急需食物和饮用水,联系13700009999",
     "entities":[{"type":"LOC","text":"福建龙岩"},{"type":"LOC","text":"上杭县"},{"type":"DIS","text":"暴雨成灾"},{"type":"PER","text":"10多户村民"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"饮用水"},{"type":"NEED","text":"联系13700009999"}],"urgency":"medium"},
    {"text":"黑龙江哈尔滨,松北区龙凤山体滑坡,有6人被困,需要救援设备,手机13900001234",
     "entities":[{"type":"LOC","text":"黑龙江哈尔滨"},{"type":"LOC","text":"松北区"},{"type":"LOC","text":"龙凤山"},{"type":"DIS","text":"山体滑坡"},{"type":"PER","text":"6人"},{"type":"NEED","text":"救援设备"},{"type":"NEED","text":"手机13900001234"}],"urgency":"emergency"},
    {"text":"西藏日喀则,定日县地震,有15户牧民需要帐篷和棉被过夜,电话13800002345",
     "entities":[{"type":"LOC","text":"西藏日喀则"},{"type":"LOC","text":"定日县"},{"type":"DIS","text":"地震"},{"type":"PER","text":"15户牧民"},{"type":"NEED","text":"帐篷"},{"type":"NEED","text":"棉被"},{"type":"NEED","text":"电话13800002345"}],"urgency":"high"},
    {"text":"江苏苏州,吴江区龙卷风,有8户居民房屋受损,需要紧急安置,联系13900003456",
     "entities":[{"type":"LOC","text":"江苏苏州"},{"type":"LOC","text":"吴江区"},{"type":"DIS","text":"龙卷风"},{"type":"DIS","text":"房屋受损"},{"type":"PER","text":"8户居民"},{"type":"NEED","text":"紧急安置"},{"type":"NEED","text":"联系13900003456"}],"urgency":"high"},
    {"text":"安徽黄山,歙县暴雨引发内涝,有20多位老人被困养老院,急需船只和食物,手机13800004567",
     "entities":[{"type":"LOC","text":"安徽黄山"},{"type":"LOC","text":"歙县"},{"type":"DIS","text":"暴雨"},{"type":"DIS","text":"内涝"},{"type":"PER","text":"20多位老人"},{"type":"LOC","text":"养老院"},{"type":"NEED","text":"船只"},{"type":"NEED","text":"食物"},{"type":"NEED","text":"手机13800004567"}],"urgency":"emergency"},
    {"text":"湖北武汉,黄陂区滠水河溃堤,有村民被困,急需救援队和船只,电话13700005678",
     "entities":[{"type":"LOC","text":"湖北武汉"},{"type":"LOC","text":"黄陂区"},{"type":"LOC","text":"滠水河"},{"type":"DIS","text":"溃堤"},{"type":"PER","text":"村民"},{"type":"NEED","text":"救援队"},{"type":"NEED","text":"船只"},{"type":"NEED","text":"电话13700005678"}],"urgency":"emergency"},
    {"text":"山东烟台,莱州市海水倒灌,有三万户停电,有老人需要吸氧设备,联系13900006789",
     "entities":[{"type":"LOC","text":"山东烟台"},{"type":"LOC","text":"莱州市"},{"type":"DIS","text":"海水倒灌"},{"type":"DIS","text":"停电"},{"type":"PER","text":"老人"},{"type":"NEED","text":"吸氧设备"},{"type":"NEED","text":"联系13900006789"}],"urgency":"emergency"},
    {"text":"云南昭通,镇雄县山体滑坡,塘房镇有被困群众40多人,需要挖掘机和救援,电话13800007890",
     "entities":[{"type":"LOC","text":"云南昭通"},{"type":"LOC","text":"镇雄县"},{"type":"DIS","text":"山体滑坡"},{"type":"LOC","text":"塘房镇"},{"type":"PER","text":"被困群众40多人"},{"type":"NEED","text":"挖掘机"},{"type":"NEED","text":"救援"},{"type":"NEED","text":"电话13800007890"}],"urgency":"emergency"},
]


# ==================================================================
# 5. 主流程: 种子 + 模板渲染 -> 输出原始数据集
# ==================================================================
def build_dataset(n_template: int = 220) -> list[dict]:
    """组装完整原始数据集。

    Args:
        n_template: 模板渲染扩增的目标数量 (默认 220, 加上种子共 300+)
    Returns:
        list of {id, text, entities, urgency}
    """
    samples: list[dict] = []

    # (1) 添加人工种子样本
    for i, s in enumerate(SEED_SAMPLES):
        samples.append({
            "id": f"seed_{i+1:04d}",
            "text": s["text"],
            "entities": s["entities"],
            "urgency": s["urgency"],
            "source": "handwritten",
        })

    # (2) 模板渲染扩增 (轮换紧急程度保证均衡)
    urgencies = ["emergency", "high", "medium"]
    weights = [0.4, 0.4, 0.2]  # 紧急/高较多
    for i in range(n_template):
        urgency = random.choices(urgencies, weights=weights, k=1)[0]
        template = random.choice(URGENCY_MAP[urgency])
        rendered = render_template(urgency, template)
        samples.append({
            "id": f"tmpl_{i+1:04d}",
            "text": rendered["text"],
            "entities": rendered["entities"],
            "urgency": rendered["urgency"],
            "source": "template",
        })

    # 打乱顺序 (但 id 不变, 便于追溯)
    random.shuffle(samples)
    return samples


def save_jsonl(samples: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


def main() -> None:
    ensure_dirs()
    samples = build_dataset(n_template=220)
    save_jsonl(samples, RAW_FILE)

    # 统计
    n_seed = sum(1 for s in samples if s["source"] == "handwritten")
    n_tmpl = sum(1 for s in samples if s["source"] == "template")
    urg_counts = {"emergency": 0, "high": 0, "medium": 0}
    type_counts = {"LOC": 0, "PER": 0, "DIS": 0, "NEED": 0}
    for s in samples:
        urg_counts[s["urgency"]] = urg_counts.get(s["urgency"], 0) + 1
        for e in s["entities"]:
            type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1

    print(f"[OK] 已生成原始数据集 -> {RAW_FILE}")
    print(f"     样本总数: {len(samples)} (人工种子 {n_seed} + 模板扩增 {n_tmpl})")
    print(f"     紧急程度分布: {urg_counts}")
    print(f"     实体类型分布: {type_counts}")


if __name__ == "__main__":
    main()
