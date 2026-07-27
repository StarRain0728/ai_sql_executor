from typing import Any, Optional
from pydantic import BaseModel, Field


class UserInfo(BaseModel):
    user_name: str = Field(alias="realName")
    user_code: str = Field(alias="userName")
    dept_id: str = Field(alias="deptId", default="")
    dept_name: str = Field(alias="deptName", default="")


class BaseResponse(BaseModel):
    success: int
    error_code: str
    error_message: str
    data: Any
    error_detail: dict[str, Any] = Field(default_factory=dict)


class BaseRequest(BaseModel):
    user_info: Optional[UserInfo] = None
