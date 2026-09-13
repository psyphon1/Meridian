from sqlalchemy.orm import DeclarativeBase

from packages.models.base import (
    Base,
    CreatedAtMixin,
    FindingSeverity,
    InstallationStatus,
    PRState,
    ReviewStatus,
    RiskTier,
    TimestampMixin,
)


def test_base_is_declarative():
    assert issubclass(Base, DeclarativeBase)


def test_timestamp_mixin_has_annotations():
    anns = TimestampMixin.__annotations__
    assert "created_at" in anns
    assert "updated_at" in anns


def test_created_at_mixin_has_annotations():
    anns = CreatedAtMixin.__annotations__
    assert "created_at" in anns
    assert "updated_at" not in anns


def test_enums_have_expected_members():
    assert ReviewStatus.RECEIVED == "RECEIVED"
    assert ReviewStatus.COMPLETED == "COMPLETED"
    assert RiskTier.HIGH == "HIGH"
    assert FindingSeverity.BLOCKING == "BLOCKING"
    assert FindingSeverity.NIT == "NIT"
    assert InstallationStatus.ACTIVE == "active"
    assert InstallationStatus.UNINSTALLED == "uninstalled"
    assert PRState.OPEN == "open"
    assert PRState.CLOSED == "closed"
