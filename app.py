"""
app.py
------
Flask application factory for the Trekking Management Application.

Usage:
    # Run the dev server
    python app.py
    # Or with Flask CLI
    flask --app app run --debug
"""

import os
from datetime import datetime, timezone
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from models__1 import db, User, AccountStatus


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
class Config:
    """Base configuration — override in subclasses for prod/testing."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    # DB lives in the instance/ folder (auto-created by Flask)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'trekking.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads (profile pics, trek images)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


# Map name → class (used by APP_ENV env var)
config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
}


# ---------------------------------------------------------------------------
# LOGIN MANAGER
# ---------------------------------------------------------------------------

login_manager = LoginManager()
login_manager.login_view = "auth.login"          # redirect here if @login_required fails
login_manager.login_message  = "Please log in to access this page."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login callback — load user from DB by primary key."""
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# APPLICATION FACTORY
# ---------------------------------------------------------------------------

def create_app(config_name: str = None) -> Flask:
    """
    Create and configure the Flask application.
    Args:
        config_name: 'development' | 'production' (defaults to APP_ENV env var
         or 'development' if not set).
    Returns:
        Configured Flask app instance.
    """
    app = Flask(__name__, instance_relative_config=True)

    # ------------------------------------------------------------------
    # Load config
    # ------------------------------------------------------------------
    if config_name is None:
        config_name = os.environ.get("APP_ENV", "development")
    app.config.from_object(config_map.get(config_name, DevelopmentConfig))

    # Ensure the instance folder exists (SQLite DB lives here)
    os.makedirs(app.instance_path, exist_ok=True)

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ------------------------------------------------------------------
    # Initialise extensions
    # ------------------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)

    # ------------------------------------------------------------------
    # Register blueprints
    # ------------------------------------------------------------------
    _register_blueprints(app)

    # ------------------------------------------------------------------
    # Register template helpers (Jinja2 globals / filters)
    # ------------------------------------------------------------------
    _register_template_helpers(app)

    # ------------------------------------------------------------------
    # Root redirect  →  smart landing based on login state
    # ------------------------------------------------------------------
    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return _role_redirect(current_user)
        return redirect(url_for("auth.login"))

    return app


# ---------------------------------------------------------------------------
# BLUEPRINT REGISTRATION
# ---------------------------------------------------------------------------
def _register_blueprints(app: Flask) -> None:
    """Import and register all blueprints."""

    # Auth (login / register / logout) — no URL prefix
    from blueprints.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    # Admin dashboard
    from blueprints.admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Trek Staff dashboard
    from blueprints.staff.routes import staff_bp
    app.register_blueprint(staff_bp, url_prefix="/staff")

    # Trekker (user) dashboard
    from blueprints.user.routes import user_bp
    app.register_blueprint(user_bp, url_prefix="/user")

    # Api registration
    from blueprints.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")


# ---------------------------------------------------------------------------
# TEMPLATE HELPERS
# ---------------------------------------------------------------------------

def _register_template_helpers(app: Flask) -> None:
    """Register Jinja2 globals and filters available in every template."""

    from models__1 import TrekStatus, BookingStatus, AccountStatus, Role

    # Expose enum classes directly in templates
    # Usage: {{ TrekStatus.OPEN }}
    app.jinja_env.globals.update(
        TrekStatus=TrekStatus,
        BookingStatus=BookingStatus,
        AccountStatus=AccountStatus,
        Role=Role,
    )

    # ----------------------------------------------------------------
    # Custom filters
    # ----------------------------------------------------------------

    @app.template_filter("currency")
    def currency_filter(value):
        """Format float as Indian Rupee string. {{ 8500.0 | currency }}"""
        try:
            return f"₹{value:,.2f}"
        except (TypeError, ValueError):
            return "₹0.00"

    @app.template_filter("dateformat")
    def dateformat_filter(value, fmt="%d %b %Y"):
        """Format a date/datetime object. {{ trek.start_date | dateformat }}"""
        if value is None:
            return "—"
        try:
            return value.strftime(fmt)
        except AttributeError:
            return str(value)

    @app.template_filter("pluralise")
    def pluralise_filter(count, singular, plural=None):
        """{{ count | pluralise('slot') }}  →  '3 slots' / '1 slot'"""
        plural = plural or (singular + "s")
        return f"{count} {singular if count == 1 else plural}"

    # ----------------------------------------------------------------
    # Context processor — injects vars into every template
    # ----------------------------------------------------------------

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        unread_count = 0
        if current_user.is_authenticated:
            unread_count = current_user.notifications.filter_by(
                is_read=False
            ).count()
        return {
            "unread_notifications": unread_count,
            "now": datetime.now(timezone.utc),
        }


# ---------------------------------------------------------------------------
# ROLE-BASED REDIRECT HELPER (shared by auth + root route)
# ---------------------------------------------------------------------------

def _role_redirect(user: User):
    """Return the correct redirect response based on the user's role."""
    from models__1 import Role
    if user.role == Role.ADMIN:
        return redirect(url_for("admin.dashboard"))
    if user.role == Role.STAFF:
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("user.dashboard"))


# ---------------------------------------------------------------------------
# ENTRY POINT  (python app.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_app("development")
    app.run(debug=True, host="0.0.0.0", port=5000)
