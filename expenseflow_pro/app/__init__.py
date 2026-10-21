import os
from pathlib import Path
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    upload_dir = Path(app.root_path) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me-before-deployment"),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + str(Path(app.instance_path) / "expenseflow.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        UPLOAD_FOLDER=str(upload_dir),
        ALLOWED_EXTENSIONS={"png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp", "pdf"},
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "info"

    from . import models
    # Register the loader explicitly during app creation. This keeps Flask-Login
    # configured even if import order changes while the project is extended.
    login_manager.user_loader(models.load_user)

    from .auth import auth_bp
    from .main import main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    return app
