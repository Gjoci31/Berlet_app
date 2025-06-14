from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
import os
from dotenv import load_dotenv

# Load environment variables from a .env file if present. This allows the
# application to retrieve email credentials and other configuration values
# without requiring them to be set in the system environment.
load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='devkey',
        SQLALCHEMY_DATABASE_URI='sqlite:///../instance/passes.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app)

    from .routes.auth_routes import auth_bp
    from .routes.user_routes import user_bp
    from .routes.admin_routes import admin_bp
    from .routes.event_routes import event_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(event_bp)

    # Ensure the database and required tables exist. Without this, a new
    # deployment would raise ``OperationalError`` when a route queries a
    # table that hasn't been created yet, resulting in a 500 error.
    #
    # ``db.create_all()`` only creates tables that do not already exist and
    # does not add new columns to existing tables. The application recently
    # introduced a ``color`` column on the ``Event`` model which older
    # databases may lack. Attempting to query such a database causes a
    # ``sqlite3.OperationalError: no such column: event.color`` and results in
    # a 500 error when the calendar page is opened.  To provide a smooth
    # upgrade path without requiring a manual migration step, check for the
    # column and add it if missing.
    with app.app_context():
        db.create_all()

        # ``PRAGMA table_info`` returns the columns of the given table.  When
        # the ``color`` column is absent, execute an ``ALTER TABLE`` statement
        # to add it with the default value ``'blue'`` so existing rows remain
        # valid and future queries succeed.
        # SQLAlchemy 2 removed the ``Engine.execute`` helper.  Use an explicit
        # connection so this code works on newer versions while remaining
        # compatible with SQLAlchemy 1.x.
        from sqlalchemy import text

        with db.engine.connect() as conn:
            insp = conn.execute(text("PRAGMA table_info(event)"))
            columns = [row[1] for row in insp]
            if 'color' not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE event ADD COLUMN color VARCHAR(20) DEFAULT 'blue'"
                    )
                )
                conn.commit()
            insp.close()

            insp = conn.execute(text("PRAGMA table_info(email_settings)"))
            columns = [row[1] for row in insp]
            if 'event_signup_user_enabled' not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE email_settings ADD COLUMN event_signup_user_enabled BOOLEAN DEFAULT 0"
                    )
                )
            if 'event_signup_user_text' not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE email_settings ADD COLUMN event_signup_user_text TEXT"
                    )
                )
            if 'event_signup_admin_enabled' not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE email_settings ADD COLUMN event_signup_admin_enabled BOOLEAN DEFAULT 0"
                    )
                )
            if 'event_signup_admin_text' not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE email_settings ADD COLUMN event_signup_admin_text TEXT"
                    )
                )
            conn.commit()
            insp.close()

    return app
