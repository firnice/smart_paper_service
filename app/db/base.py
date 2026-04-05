try:
    from sqlalchemy.orm import declarative_base
except ImportError:  # pragma: no cover
    from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
