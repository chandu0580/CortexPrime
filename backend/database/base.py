"""
SQLAlchemy DeclarativeBase shared by all ORM models.
Import this module — never import Base from individual model files —
to keep the metadata registry singleton consistent.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide declarative base."""
