"""
Shared test setup used by all test files.
"""

import pytest
from app import create_app
from config import Config
from models import db as _db


class TestConfig(Config):
    """
    Overriding settings so tests use a temporary in-memory database
    instead of messing with the actual one
    """
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret'


@pytest.fixture()
def app():
    """Creating a fresh app for each test"""
    app = create_app(TestConfig)

    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture()
def client(app):
    """A test client that can send fake HTTP requests to the app."""
    return app.test_client()