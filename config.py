import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///skillbridge.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max file upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
