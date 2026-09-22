"""Explicit development targets and secret-safe connection configuration."""

import re
from pathlib import Path
from typing import Literal

import psycopg
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
WarehousePurpose = Literal["admin", "loader"]


class WarehouseSettings(BaseSettings):
    """Load only the dedicated warehouse configuration, never frontend settings."""

    model_config = SettingsConfigDict(env_prefix="WAREHOUSE_", extra="forbid")

    purpose: WarehousePurpose = "admin"
    environment: Literal["development", "test"]
    project_ref: str = Field(pattern=r"^[a-z]{20}$")
    host: str
    port: int = Field(default=5432, ge=5432, le=5432)
    database: Literal["postgres"] = "postgres"
    user: str
    password: SecretStr = Field(repr=False)
    sslrootcert: Path

    @field_validator("password")
    @classmethod
    def require_password(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value() or value.get_secret_value() == "REPLACE_ME":
            raise ValueError("Set the database password privately before connecting")
        return value

    @model_validator(mode="after")
    def validate_target(self) -> "WarehouseSettings":
        username = "postgres" if self.purpose == "admin" else "commercelens_ingest"
        direct = self.host == f"db.{self.project_ref}.supabase.co" and self.user == username
        session = (
            re.fullmatch(r"aws-\d+-[a-z0-9-]+\.pooler\.supabase\.com", self.host)
            and self.user == f"{username}.{self.project_ref}"
        )
        if not direct and not session:
            raise ValueError(
                "Host and purpose-specific user must match the explicit project target"
            )
        return self

    def certificate_path(self, root: Path = ROOT) -> Path:
        path = self.sslrootcert if self.sslrootcert.is_absolute() else root / self.sslrootcert
        if not path.is_file():
            raise ValueError("The configured trusted CA certificate file is missing")
        return path


def load_settings(root: Path = ROOT, *, purpose: WarehousePurpose = "admin") -> WarehouseSettings:
    """Use a purpose-specific ignored file, with validated environment overrides.

    Loading never searches the administration file for missing loader credentials.
    A purpose override must agree with the command as well as its allowed username.
    """
    filename = ".env.warehouse" if purpose == "admin" else ".env.warehouse.loader"
    settings = WarehouseSettings(_env_file=root / filename, _env_file_encoding="utf-8")
    if settings.purpose != purpose:
        raise ValueError("Warehouse configuration purpose does not match the requested operation")
    return settings


def connect(settings: WarehouseSettings) -> psycopg.Connection:
    """Validate certificate and hostname; never fall back to weaker TLS."""
    return psycopg.connect(
        host=settings.host,
        port=settings.port,
        dbname=settings.database,
        user=settings.user,
        password=settings.password.get_secret_value(),
        sslmode="verify-full",
        sslrootcert=str(settings.certificate_path()),
        connect_timeout=10,
        application_name=f"commercelens-warehouse-{settings.purpose}",
        options="-c statement_timeout=60000 -c lock_timeout=10000 "
        "-c idle_in_transaction_session_timeout=60000",
        autocommit=True,
    )
