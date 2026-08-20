from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

settings = get_settings()

# MySQL连接配置
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG
)

# SQLite WAL 模式，减少锁定
if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
    # SQLite 字段迁移：natural_language_input -> input_data
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(ai_decisions)"))
            columns = [row[1] for row in result.fetchall()]
            if "natural_language_input" in columns and "input_data" not in columns:
                # 先复制数据
                conn.execute(text("UPDATE ai_decisions SET input_data = natural_language_input WHERE input_data IS NULL"))
                conn.commit()
                # 再重命名列
                conn.execute(text("ALTER TABLE ai_decisions RENAME COLUMN natural_language_input TO input_data"))
                conn.commit()
            elif "natural_language_input" in columns and "input_data" in columns:
                # 两列都存在，复制数据后删除旧列
                conn.execute(text("UPDATE ai_decisions SET input_data = natural_language_input WHERE input_data IS NULL AND natural_language_input IS NOT NULL"))
                conn.commit()
    except Exception as e:
        print(f"Migration warning: {e}")
