"""
测试AI辅助决策工作流
"""
import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000"


async def test_ai_decision_workflow():
    """测试AI决策工作流"""
    
    # 测试用例：自然语言灾情输入
    test_input = """
    红色暴雨预警，我市发生特大洪涝灾害。
    受灾人口约5000人，已有3人遇难，10人受伤。
    多条道路中断，5座桥梁受损。
    预计受灾面积50平方公里。
    当前有3家医院可用，需要紧急救援。
    """
    
    async with httpx.AsyncClient() as client:
        print("=" * 60)
        print("测试AI辅助决策工作流")
        print("=" * 60)
        
        # 1. 创建AI决策
        print("\n1. 发送自然语言灾情输入...")
        response = await client.post(
            f"{BASE_URL}/api/ai/decision",
            json={
                "natural_language_input": test_input,
                "disaster_event_id": None
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 决策创建成功，ID: {result['id']}")
            decision_id = result['id']
            
            # 2. 查看完整结果
            print("\n2. 查看工作流结果...")
            print(f"\n【自然语言输入】")
            print(result.get('natural_language_input', 'N/A')[:100] + "...")
            
            print(f"\n【AI信息抽取】")
            extracted = result.get('extracted_info')
            if extracted:
                print(json.dumps(extracted, ensure_ascii=False, indent=2))
            
            print(f"\n【风险评估】")
            risk = result.get('risk_assessment')
            if risk:
                print(json.dumps(risk, ensure_ascii=False, indent=2))
            
            print(f"\n【案例匹配】")
            cases = result.get('matched_cases')
            if cases:
                print(json.dumps(cases, ensure_ascii=False, indent=2))
            
            print(f"\n【资源需求预测】")
            resources = result.get('resource_prediction')
            if resources:
                print(json.dumps(resources, ensure_ascii=False, indent=2))
            
            print(f"\n【处置方案】")
            plan = result.get('response_plan')
            if plan:
                print(plan[:500] + "..." if len(plan) > 500 else plan)
            
            print(f"\n【指挥命令】")
            commands = result.get('command_orders')
            if commands:
                print(json.dumps(commands, ensure_ascii=False, indent=2))
            
            # 3. 确认决策
            print("\n3. 确认决策...")
            confirm_response = await client.patch(
                f"{BASE_URL}/api/ai/decisions/{decision_id}/confirm"
            )
            if confirm_response.status_code == 200:
                print(f"✓ 决策已确认")
            
            # 4. 获取决策列表
            print("\n4. 获取决策列表...")
            list_response = await client.get(f"{BASE_URL}/api/ai/decisions")
            if list_response.status_code == 200:
                decisions = list_response.json()
                print(f"✓ 共有 {len(decisions)} 条决策记录")
                
        else:
            print(f"✗ 请求失败: {response.status_code}")
            print(response.text)


if __name__ == "__main__":
    asyncio.run(test_ai_decision_workflow())
