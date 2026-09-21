from app.db.session import Base
from app.models.user import User


def test_user_model_is_registered():
    assert User.__tablename__ == "users"
    assert "users" in Base.metadata.tables


def test_user_table_has_required_columns():
    columns = Base.metadata.tables["users"].columns

    assert {
        "id",
        "username",
        "password_hash",
        "is_active",
        "created_at",
        "updated_at",
    }.issubset(columns.keys())


def test_username_is_unique():
    table = Base.metadata.tables["users"]

    assert any(
        constraint.name == "uq_users_username"
        for constraint in table.constraints
    ) or any(
        column.name == "username" and column.unique
        for column in table.columns
    )
