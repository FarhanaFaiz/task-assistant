
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database():
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "updated_at" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN updated_at DATETIME "
                        "NOT NULL DEFAULT CURRENT_TIMESTAMP"
                    )
                )
    if "tasks" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("tasks")}
        migrations = {
            "priority": "ALTER TABLE tasks ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'medium'",
            "due_date": "ALTER TABLE tasks ADD COLUMN due_date DATETIME",
            "category": "ALTER TABLE tasks ADD COLUMN category VARCHAR(100)",
            "estimated_minutes": "ALTER TABLE tasks ADD COLUMN estimated_minutes INTEGER",
            "updated_at": "ALTER TABLE tasks ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        }
        missing = [sql for column, sql in migrations.items() if column not in columns]
        if missing:
            with engine.begin() as connection:
                for sql in missing:
                    connection.execute(text(sql))
    inspector = inspect(engine)
    if "tasks" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("tasks")}
        if "goal_id" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE tasks ADD COLUMN goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL")
                )
        columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
        if "milestone_id" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE tasks ADD COLUMN milestone_id INTEGER "
                        "REFERENCES milestones(id) ON DELETE SET NULL"
                    )
                )
