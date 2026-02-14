from flask import Flask
from app.extensions import db, login_manager, csrf
import os


def create_app():
    app = Flask(__name__)

    # Configuration
    debug_env = os.environ.get("FLASK_DEBUG") == "1"
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if debug_env:
            secret_key = "chainport-dev-secret-change-in-production"
        else:
            # Avoid a static secret in non-debug runs.
            secret_key = os.urandom(32).hex()
    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        os.environ.get("DATABASE_URL") or "sqlite:///chainport.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    app.config["MESSAGE_UPLOAD_FOLDER"] = os.path.join(
        app.instance_path, "uploads", "messages"
    )
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size
    app.config["MESSAGE_ATTACHMENT_LIMIT"] = 5
    app.config["ALLOWED_EXTENSIONS"] = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["MESSAGE_UPLOAD_FOLDER"], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Login manager configuration
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User

        return db.session.get(User, int(user_id))

    # Register blueprints
    from app.routes import main_bp

    app.register_blueprint(main_bp)

    from app.auth import auth_bp

    app.register_blueprint(auth_bp)

    # Create database tables
    with app.app_context():
        db.create_all()

    # Make csrf_token available in templates
    @app.context_processor
    def inject_csrf_token():
        def csrf_token():
            from flask_wtf.csrf import generate_csrf

            return generate_csrf()

        return dict(csrf_token=csrf_token)

    return app
