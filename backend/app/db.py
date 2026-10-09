from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import BACKEND_DIR

DB_PATH = BACKEND_DIR / "app.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    # Additive migration for databases created by the original workbench.
    if "workflow_options" not in {c["name"] for c in inspect(engine).get_columns("projects")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE projects ADD COLUMN workflow_options JSON"))
