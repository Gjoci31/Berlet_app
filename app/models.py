from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='user')  # 'admin' or 'user'
    passes = db.relationship('Pass', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

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

