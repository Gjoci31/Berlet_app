from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    # Store the plain password for reminder emails. This is insecure but
    # required for the current application logic.
    password_plain = db.Column(db.String(150))
    role = db.Column(db.String(10), nullable=False, default='user')  # 'admin' or 'user'
    # Delete associated passes when a user is removed so foreign key
    # constraints don't raise an ``IntegrityError``.
    passes = db.relationship(
        'Pass', backref='user', lazy=True, cascade='all, delete-orphan'
    )
    event_registrations = db.relationship(
        'EventRegistration', backref='user', lazy=True, cascade='all, delete-orphan'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_plain = password

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Pass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.Date, nullable=False)
    total_uses = db.Column(db.Integer, nullable=False)
    used = db.Column(db.Integer, default=0)
    comment = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usages = db.relationship(
        'PassUsage', backref='pass_ref', lazy=True, cascade='all, delete-orphan'
    )


class PassUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pass_id = db.Column(db.Integer, db.ForeignKey('pass.id'), nullable=False)
    used_on = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class EmailSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_from = db.Column(db.String(150))
    email_password = db.Column(db.String(150))

    user_created_enabled = db.Column(db.Boolean, default=False)
    user_created_text = db.Column(db.Text)

    user_deleted_enabled = db.Column(db.Boolean, default=False)
    user_deleted_text = db.Column(db.Text)

    pass_created_enabled = db.Column(db.Boolean, default=False)
    pass_created_text = db.Column(db.Text)

    pass_deleted_enabled = db.Column(db.Boolean, default=False)
    pass_deleted_text = db.Column(db.Text)

    pass_used_enabled = db.Column(db.Boolean, default=False)
    pass_used_text = db.Column(db.Text)


class Event(db.Model):
    """Calendar event which users can sign up for."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    registrations = db.relationship(
        'EventRegistration', backref='event', lazy=True, cascade='all, delete-orphan'
    )

    @property
    def spots_left(self) -> int:
        return self.capacity - len(self.registrations)


class EventRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User')


