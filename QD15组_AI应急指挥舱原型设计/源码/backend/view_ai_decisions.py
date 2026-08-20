"""
查看AI决策数据库记录
"""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "emergency_command.db"


def view_ai_decisions():
    """查看AI决策记录"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 查询所有AI决策记录
    cursor.execute("SELECT * FROM ai_decisions ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    print(f"\n{'='*80}")
    print(f"AI决策记录 (共 {len(rows)} 条)")
    print(f"{'='*80}\n")
    
    for i, row in enumerate(rows, 1):
        print(f"--- 记录 {i} ---")
        print(f"ID: {row['id']}")
        print(f"灾情事件ID: {row['disaster_event_id']}")
        print(f"\n【自然语言输入】")
        print(row['natural_language_input'][:100] + "..." if row['natural_language_input'] else "N/A")
        
        print(f"\n【AI信息抽取】")
        if row['extracted_info']:
            info = json.loads(row['extracted_info'])
            print(json.dumps(info, ensure_ascii=False, indent=2))
        
        print(f"\n【风险评估】")
        if row['risk_assessment']:
            risk = json.loads(row['risk_assessment'])
            print(json.dumps(risk, ensure_ascii=False, indent=2))
        
        print(f"\n【案例匹配】")
        if row['matched_cases']:
            cases = json.loads(row['matched_cases'])
            print(json.dumps(cases, ensure_ascii=False, indent=2))
        
        print(f"\n【资源需求预测】")
        if row['resource_prediction']:
            resources = json.loads(row['resource_prediction'])
            print(json.dumps(resources, ensure_ascii=False, indent=2))
        
        print(f"\n【处置方案】")
        if row['response_plan']:
            print(row['response_plan'][:300] + "..." if len(row['response_plan']) > 300 else row['response_plan'])
        
        print(f"\n【指挥命令】")
        if row['command_orders']:
            commands = json.loads(row['command_orders'])
            print(json.dumps(commands, ensure_ascii=False, indent=2))
        
        print(f"\n状态: {row['status']}")
        print(f"创建时间: {row['created_at']}")
        print(f"\n{'='*80}\n")
    
    conn.close()


if __name__ == "__main__":
    view_ai_decisions()
