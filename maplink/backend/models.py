"""Validated API payloads. Never trust coordinates, amounts or player IDs from a client UI."""
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

class ServerIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    display_name: str = Field(min_length=2, max_length=80)
    map_name: str = Field(min_length=2, max_length=80)
    host: str = Field(min_length=3, max_length=255)
    game_port: int = Field(ge=1, le=65535)

class TicketIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    name: str = Field(min_length=1, max_length=80)
    classname: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_]+$")
    quantity: int = Field(default=1, ge=1, le=1000)
    consume_on_departure: bool = True

class VideoIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    name: str = Field(min_length=1, max_length=80)
    departure_asset: str = Field(default="", max_length=160)
    arrival_asset: str = Field(default="", max_length=160)

    @field_validator("departure_asset", "arrival_asset")
    @classmethod
    def safe_asset(cls, value: str):
        if value and ("/" in value or "\\" in value or ".." in value or not value.lower().endswith(".mp4")):
            raise ValueError("Use an .mp4 filename included in the client mod, without paths")
        return value

class RouteIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    name: str = Field(min_length=2, max_length=80)
    source_server_id: str
    target_server_id: str
    ticket_id: str | None = None
    video_id: str | None = None
    currency_classname: str | None = None
    price: int = Field(default=0, ge=0)
    spawn_x: float = 0
    spawn_y: float = 0
    spawn_z: float = 0
    enabled: bool = True

    @model_validator(mode="after")
    def no_loop(self):
        if self.source_server_id == self.target_server_id:
            raise ValueError("Source and destination must differ")
        if self.price and not self.currency_classname:
            raise ValueError("currency_classname is required when price > 0")
        return self

class TerminalIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    server_id: str
    name: str = Field(min_length=2, max_length=80)
    classname: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_]+$")
    x: float
    y: float
    z: float
    radius: float = Field(default=3.0, gt=0, le=25)
    auto_spawn: bool = False
    enabled: bool = True
    route_ids: list[str] = Field(default_factory=list, max_length=64)

class PrepareIn(BaseModel):
    transfer_id: str
    steam_id: str = Field(min_length=8, max_length=48)
    route_id: str
    snapshot: dict[str, Any]
    # Must be attested by trusted game server AFTER actual inventory/currency checks.
    ticket_verified: bool = False
    payment_verified: bool = False

class TransferIdIn(BaseModel):
    transfer_id: str

class ResolveIn(BaseModel):
    action: Literal["cancel_prepared"]
