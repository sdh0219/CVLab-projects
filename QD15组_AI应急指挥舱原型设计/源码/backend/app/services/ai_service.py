"""AI决策服务 - 完整工作流：自然语言输入 → 信息抽取 → 风险评估 → 案例匹配 → 资源预测 → 处置方案 → 指挥命令"""
from openai import AsyncOpenAI
from app.config import get_settings
import json
import re
from datetime import datetime

settings = get_settings()


async def get_ai_decision_workflow(natural_language_input: str) -> dict:
    """
    完整的AI辅助决策工作流
    
    工作流:
    1. 自然语言灾情输入
    2. AI信息抽取
    3. 风险评估
    4. 案例匹配(RAG)
    5. 资源需求预测
    6. 生成处置方案
    7. 生成指挥命令
    """
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    try:
        # 步骤1-2: 信息抽取
        extracted_info = await _extract_information(client, natural_language_input)
        
        # 步骤3: 风险评估
        risk_assessment = await _assess_risk(client, extracted_info)
        
        # 步骤4: 案例匹配(RAG)
        matched_cases = await _match_cases(client, extracted_info)
        
        # 步骤5: 资源需求预测
        resource_prediction = await _predict_resources(client, extracted_info, risk_assessment)
        
        # 步骤6: 生成处置方案
        response_plan = await _generate_response_plan(
            client, extracted_info, risk_assessment, matched_cases, resource_prediction
        )
        
        # 步骤7: 生成指挥命令
        command_orders = await _generate_commands(client, response_plan, extracted_info)
        
        return {
            "extracted_info": extracted_info,
            "risk_assessment": risk_assessment,
            "matched_cases": matched_cases,
            "resource_prediction": resource_prediction,
            "response_plan": response_plan,
            "command_orders": command_orders,
            "full_response": json.dumps({
                "extracted_info": extracted_info,
                "risk_assessment": risk_assessment,
                "matched_cases": matched_cases,
                "resource_prediction": resource_prediction,
                "response_plan": response_plan,
                "command_orders": command_orders
            }, ensure_ascii=False, indent=2)
        }
        
    except Exception as e:
        # API调用失败时返回模拟结果
        return _generate_mock_workflow(natural_language_input)


async def _extract_information(client: AsyncOpenAI, text: str) -> dict:
    """步骤2: 从自然语言中抽取结构化灾情信息"""
    prompt = f"""你是一个应急信息抽取专家。请从以下灾情描述中抽取关键信息，以JSON格式返回：

灾情描述：
{text}

请抽取以下信息（如果未提及则填null）：
{{
    "disaster_type": "灾害类型（flood/earthquake/forest_fire/extreme_weather）",
    "location": "灾害发生地点",
    "time": "发生时间",
    "warning_level": "预警等级（red/orange/yellow/blue）",
    "affected_population": "受灾人口（数字）",
    "casualties": "伤亡人数（数字）",
    "affected_area": "受灾面积（平方公里，数字）",
    "damaged_infrastructure": "受损基础设施（列表）",
    "weather_condition": "天气状况",
    "other_details": "其他重要信息"
}}

只返回JSON，不要其他内容。"""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "你是应急信息抽取专家，擅长从自然语言中提取结构化灾情信息。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_extraction": content}


async def _assess_risk(client: AsyncOpenAI, extracted_info: dict) -> dict:
    """步骤3: 风险评估"""
    prompt = f"""你是应急风险评估专家。请根据以下抽取的灾情信息进行风险评估：

灾情信息：
{json.dumps(extracted_info, ensure_ascii=False, indent=2)}

请评估以下内容，以JSON格式返回：
{{
    "risk_level": "风险等级（I/II/III/IV，I为最高）",
    "risk_score": "风险评分（0-100）",
    "primary_risks": ["主要风险点列表"],
    "secondary_risks": ["次生灾害风险列表"],
    "impact_scope": "影响范围描述",
    "evacuation_urgency": "转移紧迫性（high/medium/low）",
    "assessment_summary": "风险评估总结"
}}

只返回JSON，不要其他内容。"""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "你是应急风险评估专家。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=1000
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_assessment": content}


async def _match_cases(client: AsyncOpenAI, extracted_info: dict) -> list:
    """步骤4: 案例匹配(RAG)"""
    prompt = f"""你是应急案例匹配专家。请根据以下灾情信息，匹配相似的历史案例：

灾情信息：
{json.dumps(extracted_info, ensure_ascii=False, indent=2)}

请匹配3-5个相似历史案例，以JSON数组格式返回：
[
    {{
        "case_id": "案例编号",
        "case_name": "案例名称",
        "disaster_type": "灾害类型",
        "similarity_score": "相似度（0-100）",
        "key_measures": ["采取的关键措施"],
        "lessons_learned": ["经验教训", "可借鉴的做法"]
    }}
]

只返回JSON数组，不要其他内容。"""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "你是应急案例匹配专家，擅长根据灾情特征匹配历史案例。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=1500
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return [{"raw_cases": content}]


async def _predict_resources(client: AsyncOpenAI, extracted_info: dict, risk_assessment: dict) -> dict:
    """步骤5: 资源需求预测"""
    prompt = f"""你是应急资源规划专家。请根据以下信息预测资源需求：

灾情信息：
{json.dumps(extracted_info, ensure_ascii=False, indent=2)}

风险评估：
{json.dumps(risk_assessment, ensure_ascii=False, indent=2)}

请预测以下资源需求，以JSON格式返回：
{{
    "rescue_teams": {{
        "firefighters": "消防员人数",
        "medical_teams": "医疗队数量",
        "search_rescue": "搜救队伍数量",
        "engineers": "工程技术人员数量"
    }},
    "materials": {{
        "tents": "帐篷数量",
        "food_rations": "食品份数",
        "water_bottles": "饮用水瓶数",
        "medical_supplies": "医疗物资套数",
        "generators": "发电机数量",
        "blankets": "毛毯数量"
    }},
    "equipment": {{
        "drones": "无人机数量",
        "vehicles": "车辆数量",
        "boats": "冲锋舟数量",
        "communication_devices": "通信设备数量"
    }},
    "prediction_summary": "资源需求预测总结"
}}

只返回JSON，不要其他内容。"""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "你是应急资源规划专家，擅长根据灾情预测资源需求。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=1000
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_prediction": content}


async def _generate_response_plan(
    client: AsyncOpenAI,
    extracted_info: dict,
    risk_assessment: dict,
    matched_cases: list,
    resource_prediction: dict
) -> str:
    """步骤6: 生成处置方案"""
    prompt = f"""你是应急指挥专家。请根据以下信息生成详细的处置方案：

灾情信息：
{json.dumps(extracted_info, ensure_ascii=False, indent=2)}

风险评估：
{json.dumps(risk_assessment, ensure_ascii=False, indent=2)}

匹配案例：
{json.dumps(matched_cases, ensure_ascii=False, indent=2)}

资源需求：
{json.dumps(resource_prediction, ensure_ascii=False, indent=2)}

请生成一份完整的处置方案，包括：
1. 应急响应等级及启动条件
2. 指挥体系建立
3. 救援力量部署
4. 群众转移安置
5. 物资调拨分配
6. 医疗救护安排
7. 基础设施抢修
8. 信息发布机制
9. 次生灾害防范

请以结构化的文本格式返回，便于阅读和执行。"""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "你是应急指挥专家，擅长制定科学合理的应急处置方案。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    return response.choices[0].message.content


async def _generate_commands(client: AsyncOpenAI, response_plan: str, extracted_info: dict) -> list:
    """步骤7: 生成指挥命令"""
    prompt = f"""你是应急指挥命令生成专家。请根据以下处置方案生成具体的指挥命令：

处置方案：
{response_plan}

灾情信息：
{json.dumps(extracted_info, ensure_ascii=False, indent=2)}

请生成具体的指挥命令列表，以JSON数组格式返回：
[
    {{
        "command_id": "命令编号",
        "command_type": "命令类型（deployment/evacuation/allocation/rescue/other）",
        "target_unit": "执行单位",
        "command_content": "命令内容",
        "priority": "优先级（high/medium/low）",
        "deadline": "完成时限",
        "reporting_requirement": "报告要求"
    }}
]

只返回JSON数组，不要其他内容。"""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "你是应急指挥命令生成专家。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=1500
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return [{"raw_commands": content}]


def _generate_mock_workflow(natural_language_input: str) -> dict:
    """生成模拟工作流结果（API不可用时使用）"""
    # 简单的关键词提取
    text_lower = natural_language_input.lower()
    
    # 灾害类型识别
    disaster_type = "flood"
    if "地震" in text_lower or "earthquake" in text_lower:
        disaster_type = "earthquake"
    elif "火灾" in text_lower or "fire" in text_lower:
        disaster_type = "forest_fire"
    elif "暴雨" in text_lower or "洪水" in text_lower or "flood" in text_lower:
        disaster_type = "flood"
    elif "台风" in text_lower or "typhoon" in text_lower:
        disaster_type = "extreme_weather"
    
    # 预警等级识别
    warning_level = "orange"
    if "红色" in text_lower or "red" in text_lower:
        warning_level = "red"
    elif "橙色" in text_lower or "orange" in text_lower:
        warning_level = "orange"
    elif "黄色" in text_lower or "yellow" in text_lower:
        warning_level = "yellow"
    elif "蓝色" in text_lower or "blue" in text_lower:
        warning_level = "blue"
    
    # 提取数字（受灾人口）
    numbers = re.findall(r'\d+', natural_language_input)
    affected_pop = int(numbers[0]) * 100 if numbers else 5000
    
    return {
        "extracted_info": {
            "disaster_type": disaster_type,
            "location": "灾区",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "warning_level": warning_level,
            "affected_population": affected_pop,
            "casualties": affected_pop // 100,
            "affected_area": affected_pop // 10,
            "damaged_infrastructure": ["道路", "桥梁", "电力"],
            "weather_condition": "恶劣天气",
            "other_details": "根据自然语言描述自动提取"
        },
        "risk_assessment": {
            "risk_level": "II" if warning_level in ["red", "orange"] else "III",
            "risk_score": 85 if warning_level == "red" else 70,
            "primary_risks": ["人员伤亡风险", "基础设施损毁风险"],
            "secondary_risks": ["次生灾害风险", "疫情风险"],
            "impact_scope": f"预计影响{affected_pop}人",
            "evacuation_urgency": "high" if warning_level == "red" else "medium",
            "assessment_summary": f"当前{warning_level}预警，风险等级较高，需立即启动应急响应"
        },
        "matched_cases": [
            {
                "case_id": "CASE-2023-001",
                "case_name": "2023年特大暴雨灾害处置",
                "disaster_type": disaster_type,
                "similarity_score": 92,
                "key_measures": ["立即启动II级响应", "组织群众转移", "调集救援力量"],
                "lessons_learned": ["提前预警很重要", "物资储备要充足", "通信保障是关键"]
            },
            {
                "case_id": "CASE-2022-015",
                "case_name": "2022年洪涝灾害应急处置",
                "disaster_type": disaster_type,
                "similarity_score": 85,
                "key_measures": ["多部门联动", "无人机侦察", "分区域转移"],
                "lessons_learned": ["跨部门协调要提前演练", "科技手段提升效率"]
            }
        ],
        "resource_prediction": {
            "rescue_teams": {
                "firefighters": max(50, affected_pop // 100),
                "medical_teams": max(5, affected_pop // 1000),
                "search_rescue": max(3, affected_pop // 2000),
                "engineers": max(10, affected_pop // 500)
            },
            "materials": {
                "tents": max(10, affected_pop // 50),
                "food_rations": affected_pop * 3,
                "water_bottles": affected_pop * 6,
                "medical_supplies": max(100, affected_pop // 10),
                "generators": max(5, affected_pop // 1000),
                "blankets": max(100, affected_pop // 10)
            },
            "equipment": {
                "drones": max(3, affected_pop // 2000),
                "vehicles": max(20, affected_pop // 200),
                "boats": max(5, affected_pop // 1000),
                "communication_devices": max(50, affected_pop // 100)
            },
            "prediction_summary": f"预计需要救援力量{max(50, affected_pop // 100)}人，帐篷{max(10, affected_pop // 50)}顶"
        },
        "response_plan": f"""【应急处置方案】

一、应急响应等级
启动II级应急响应，成立现场指挥部。

二、指挥体系
- 总指挥：应急管理局局长
- 副总指挥：消防救援支队支队长
- 成员：各相关部门负责人

三、救援力量部署
- 消防救援：{max(50, affected_pop // 100)}人
- 医疗救援：{max(5, affected_pop // 1000)}支队伍
- 搜救队伍：{max(3, affected_pop // 2000)}支
- 工程技术人员：{max(10, affected_pop // 500)}人

四、群众转移安置
- 转移人数：{affected_pop}人
- 安置点：周边学校、体育馆等
- 转移方式：分批有序转移

五、物资调拨
- 帐篷：{max(10, affected_pop // 50)}顶
- 食品：{affected_pop * 3}份
- 饮用水：{affected_pop * 6}瓶

六、医疗救护
- 设立临时医疗点
- 配备救护车{max(5, affected_pop // 1000)}辆
- 准备急救药品和器械

七、基础设施抢修
- 优先恢复通信
- 抢修受损道路
- 恢复电力供应

八、信息发布
- 定时发布灾情信息
- 回应社会关切
- 防止谣言传播

九、次生灾害防范
- 加强监测预警
- 做好防疫准备
- 防范地质灾害""",
        "command_orders": [
            {
                "command_id": "CMD-001",
                "command_type": "deployment",
                "target_unit": "消防救援支队",
                "command_content": f"立即调派{max(50, affected_pop // 100)}名消防指战员前往灾区开展救援",
                "priority": "high",
                "deadline": "2小时内",
                "reporting_requirement": "每小时报告一次进展"
            },
            {
                "command_id": "CMD-002",
                "command_type": "evacuation",
                "target_unit": "街道办事处",
                "command_content": f"组织{affected_pop}名群众有序转移至安全区域",
                "priority": "high",
                "deadline": "6小时内",
                "reporting_requirement": "每2小时报告转移进度"
            },
            {
                "command_id": "CMD-003",
                "command_type": "allocation",
                "target_unit": "物资保障组",
                "command_content": f"调拨帐篷{max(10, affected_pop // 50)}顶、食品{affected_pop * 3}份、饮用水{affected_pop * 6}瓶",
                "priority": "high",
                "deadline": "4小时内",
                "reporting_requirement": "物资到位后立即报告"
            },
            {
                "command_id": "CMD-004",
                "command_type": "rescue",
                "target_unit": "医疗救援队",
                "command_content": f"派出{max(5, affected_pop // 1000)}支医疗队伍前往灾区设立临时医疗点",
                "priority": "medium",
                "deadline": "3小时内",
                "reporting_requirement": "医疗点设立后报告"
            },
            {
                "command_id": "CMD-005",
                "command_type": "other",
                "target_unit": "通信保障组",
                "command_content": "抢修受损通信设施，保障灾区通信畅通",
                "priority": "medium",
                "deadline": "8小时内",
                "reporting_requirement": "通信恢复后报告"
            }
        ],
        "full_response": "模拟工作流结果（API不可用）"
    }
