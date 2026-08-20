import sqlite3

conn = sqlite3.connect('emergency_command.db')
c = conn.cursor()

# 检查列
c.execute("PRAGMA table_info(ai_decisions)")
columns = [row[1] for row in c.fetchall()]
print('Columns:', columns)

# 检查旧数据
c.execute("SELECT id, natural_language_input, input_data FROM ai_decisions")
rows = c.fetchall()
for row in rows:
    print(f'ID {row[0]}: old={repr(row[1])[:30]}, new={repr(row[2])[:30]}')

# 迁移数据
if 'natural_language_input' in columns:
    c.execute("UPDATE ai_decisions SET input_data = natural_language_input WHERE input_data IS NULL AND natural_language_input IS NOT NULL")
    conn.commit()
    print(f'Updated {c.rowcount} rows')
    
    # 删除旧列（SQLite 不支持直接删除列，需要重建表）
    # 暂时保留旧列，避免破坏数据

# 验证
c.execute("SELECT id, input_data FROM ai_decisions")
for row in c.fetchall():
    print(f'ID {row[0]}: input_data={repr(row[1])[:50]}')

conn.close()
