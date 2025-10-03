from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from ..models import Pass, User, db
from ..forms import PurchasePassForm
from ..utils import send_event_email
from ..email_templates import pass_created_email

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        passes = Pass.query.all()
    else:
        passes = Pass.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', passes=passes, user=current_user)


@user_bp.route('/toggle_reminder', methods=['POST'])
@login_required
def toggle_reminder():
    current_user.weekly_reminder_opt_in = not current_user.weekly_reminder_opt_in
    db.session.commit()
    next_url = request.referrer or url_for('user.dashboard')
    return redirect(next_url)


@user_bp.route('/passes/purchase', methods=['GET', 'POST'])
@login_required
def purchase_pass():
    if current_user.role == 'admin':
        return redirect(url_for('user.dashboard'))

    form = PurchasePassForm()
    if form.validate_on_submit():
        uses = int(form.pass_type.data)
        start = date.today()
        end = start + timedelta(days=90)
        new_pass = Pass(
            type=f"{uses} alkalmas bérlet",
            start_date=start,
            end_date=end,
            total_uses=uses,
            used=0,
            user_id=current_user.id,
        )
        db.session.add(new_pass)
        db.session.commit()
        send_event_email(
            'pass_created',
            'Új bérlet',
            pass_created_email(new_pass),
            current_user.email,
        )
        flash('Bérlet sikeresen megvásárolva.', 'success')
        return redirect(url_for('user.dashboard'))
    return render_template('purchase_pass.html', form=form)
