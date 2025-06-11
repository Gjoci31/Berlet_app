from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from ..models import Pass, User, db

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        passes = Pass.query.all()
    else:
        passes = Pass.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', passes=passes, user=current_user)
