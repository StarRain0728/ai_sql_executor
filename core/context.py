import contextvars
from pydantic import BaseModel, Field


class UserContext(BaseModel):
    user_code: str = Field()
    user_dept_id: str = Field(default="")
    user_name: str = Field(default="")
    user_dept_name: str = Field(default="")


_user_context: contextvars.ContextVar[UserContext] = contextvars.ContextVar("user_context")


def set_user_context(user_context: UserContext) -> contextvars.Token:
    return _user_context.set(user_context)


def get_user_context() -> UserContext:
    return _user_context.get()


def get_user_code() -> str:
    return get_user_context().user_code


def get_user_dept() -> str:
    return get_user_context().user_dept_id


def get_user_dept_name() -> str:
    return get_user_context().user_dept_name
