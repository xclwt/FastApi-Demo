from pydantic import BaseModel


class LoginBody(BaseModel):
    account: str
    password: str


class GetUserBody(BaseModel):
    account: str
    password: str
    name: str
    mobilephone: str


class UpdateUserBody(BaseModel):
    account: str
    password: str
    mobilephone: str


class GetRoleBody(BaseModel):
    name: str
    info: str


class UpdateRoleBody(BaseModel):
    name: str
    info: str


class UserRoleBody(BaseModel):
    role_id: int