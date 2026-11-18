"""项目中文名 API。"""

from __future__ import annotations

from typing import Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from work_report.api.deps import DbSession
from work_report.services import settings_service

router = APIRouter(tags=["project-names"])


class ProjectNameItem(BaseModel):
    project_id: int | None = Field(default=None, gt=0)
    project_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class ProjectNameList(BaseModel):
    items: list[ProjectNameItem]

    @model_validator(mode="after")
    def validate_unique_project_ids(self) -> Self:
        project_ids = [item.project_id for item in self.items if item.project_id is not None]
        if len(project_ids) != len(set(project_ids)):
            raise ValueError("项目 ID 不能重复")
        return self


@router.get("/project-names")
def get_project_names(db: DbSession) -> dict:
    return {"items": settings_service.list_project_names(db)}


@router.put("/project-names")
def put_project_names(body: ProjectNameList, db: DbSession) -> dict:
    items = [i.model_dump() for i in body.items]
    return {"items": settings_service.replace_project_names(db, items)}


@router.post("/project-names")
def post_project_name(body: ProjectNameItem, db: DbSession) -> dict:
    settings_service.upsert_project_name(
        db,
        body.project_key,
        body.display_name,
        body.project_id,
    )
    return {"ok": True, "item": body.model_dump()}


@router.delete("/project-names/{project_key}")
def delete_project_name(project_key: str, db: DbSession) -> dict:
    ok = settings_service.delete_project_name(db, project_key)
    if not ok:
        raise HTTPException(status_code=404, detail="项目映射不存在")
    return {"ok": True}
