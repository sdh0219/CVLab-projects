"""
数据库迁移脚本：更新ai_decisions表结构以支持新的工作流
"""
import sqlite3
from pathlib import Path

# 数据库路径
DB_PATH = Path(__file__).resolve().parent / "emergency_command.db"


def migrate_ai_decisions_table():
    """迁移ai_decisions表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_decisions'")
    if not cursor.fetchone():
        print("ai_decisions表不存在，无需迁移")
        conn.close()
        return
    
    # 获取现有列
    cursor.execute("PRAGMA table_info(ai_decisions)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    # 需要添加的新列
    new_columns = [
        ("natural_language_input", "TEXT"),
        ("extracted_info", "JSON"),
        ("matched_cases", "JSON"),
        ("resource_prediction", "JSON"),
        ("response_plan", "TEXT"),
        ("command_orders", "JSON")
    ]
    
    # 需要删除的旧列
    old_columns = [
        "input_data",
        "response_suggestion",
        "resource_deployment",
        "material_allocation",
        "evacuation_plan"
    ]
    
    print(f"现有列: {existing_columns}")
    
    # 添加新列（如果不存在）
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE ai_decisions ADD COLUMN {col_name} {col_type}")
                print(f"✓ 添加列: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"✗ 添加列 {col_name} 失败: {e}")
    
    # SQLite不支持直接删除列，需要重建表
    # 但为了简单起见，我们保留旧列，只是不再使用它们
    print("\n迁移完成！旧列将被保留但不再使用。")
    
    conn.commit()
    conn.close()
    print(f"\n数据库迁移完成: {DB_PATH}")


if __name__ == "__main__":
    migrate_ai_decisions_table()
