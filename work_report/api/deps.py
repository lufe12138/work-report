"""FastAPI 依赖。"""

from __future__ import annotations

from typing import Annotated, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from work_report.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]
