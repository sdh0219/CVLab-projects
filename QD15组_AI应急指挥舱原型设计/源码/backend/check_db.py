import sqlite3

conn = sqlite3.connect('emergency_command.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', c.fetchall())

c.execute("SELECT COUNT(*) FROM disaster_events")
print('Events:', c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM ai_decisions")
print('AI decisions:', c.fetchone()[0])

conn.close()
