import pytest

from app.core.config import DatabaseSettings


@pytest.fixture(autouse=True)
def explicit_database_host(monkeypatch):
    monkeypatch.setenv("DB_HOST", "test-db")


def test_environment_settings(monkeypatch):
    monkeypatch.setenv("DB_HOST", "test-db")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "test_database")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "5")

    settings = DatabaseSettings.from_environment()

    assert settings.host == "test-db"
    assert settings.port == 5433
    assert settings.name == "test_database"
    assert settings.user == "test_user"
    assert settings.password == "test_password"
    assert settings.connect_timeout == 5


def test_missing_password(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD", raising=False)

    with pytest.raises(KeyError):
        DatabaseSettings.from_environment()


def test_missing_host(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.delenv("DB_HOST", raising=False)

    with pytest.raises(KeyError, match="DB_HOST"):
        DatabaseSettings.from_environment()


@pytest.mark.parametrize("host", ["", " ", "\t"])
def test_blank_host(monkeypatch, host):
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_HOST", host)

    with pytest.raises(ValueError, match="DB_HOST"):
        DatabaseSettings.from_environment()


@pytest.mark.parametrize("port", ["0", "65536", "abc"])
def test_invalid_port(monkeypatch, port):
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_PORT", port)

    with pytest.raises(ValueError):
        DatabaseSettings.from_environment()
