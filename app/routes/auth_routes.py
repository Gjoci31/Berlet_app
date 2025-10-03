from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from ..models import User, db
from ..forms import LoginForm, ForgotPasswordForm, RegistrationForm
from ..utils import send_email
from ..email_templates import forgot_password_email
import secrets

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('user.dashboard'))
        flash('Hibás felhasználónév vagy jelszó.', 'danger')
    return render_template('login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Az email cím már használatban van.', 'danger')
            return render_template('register.html', form=form)
        if User.query.filter_by(username=form.username.data).first():
            flash('A felhasználónév már foglalt.', 'danger')
            return render_template('register.html', form=form)

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        user.role = 'user'
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Sikeres regisztráció. Üdvözlünk!', 'success')
        return redirect(url_for('user.dashboard'))
    return render_template('register.html', form=form)


@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """Send the user's existing password to the provided email."""
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            password = user.password_plain
            if not password:
                password = secrets.token_urlsafe(8)
                user.set_password(password)
                db.session.commit()
            send_email(
                "Elfelejtett jelszó",
                forgot_password_email(user.username, password),
                user.email,
            )
            flash('Jelszó elküldve az email címre.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Nem található felhasználó ezzel az email címmel.', 'danger')
    return render_template('forgot_password.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))
