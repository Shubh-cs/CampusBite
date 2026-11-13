import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database import Base, get_db
from app.dependencies.auth import require_roles
from app.models import User
from app.core.security import hash_password
from app.routers.auth import router as auth_router
from app.routers.owner_menu import router as owner_menu_router
from app.routers.restaurants import router as restaurants_router
from app.schemas.auth import UserPublic

TEST_JWT_SECRET = "test-only-secret-with-at-least-32-bytes"
TEST_PASSWORD = "correct-horse-battery"
auth_test_app = FastAPI()
auth_test_app.include_router(auth_router)
auth_test_app.include_router(restaurants_router)
auth_test_app.include_router(owner_menu_router)


def _role_test_endpoint(role):
    def endpoint(user: User = Depends(require_roles(role))):
        return UserPublic.model_validate(user, from_attributes=True)

    return endpoint


for _role in ("CUSTOMER", "OWNER", "DELIVERY_PARTNER"):
    auth_test_app.add_api_route(
        f"/__test__/roles/{_role.lower()}",
        _role_test_endpoint(_role),
        methods=["GET"],
        response_model=UserPublic,
    )


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = test_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr(TEST_JWT_SECRET))

    def override_get_db():
        yield db_session

    auth_test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(auth_test_app) as test_client:
        yield test_client
    auth_test_app.dependency_overrides.clear()


@pytest.fixture
def role_users(db_session):
    users = {}
    for role in ("CUSTOMER", "OWNER", "DELIVERY_PARTNER"):
        user = User(
            full_name=f"Test {role.title()}",
            email=f"{role.lower()}@example.test",
            password_hash=hash_password(TEST_PASSWORD),
            role=role,
        )
        db_session.add(user)
        users[role] = user
    db_session.commit()
    return users
