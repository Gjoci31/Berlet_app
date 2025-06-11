from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..models import Pass, User, db
from ..forms import PassForm
from ..utils import send_email

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/create_pass', methods=['GET', 'POST'])
@login_required
def create_pass():
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))

    form = PassForm()
    users = User.query.all()
    form.user_id.choices = [(u.id, u.username) for u in users]

    if form.validate_on_submit():
        new_pass = Pass(
            type=form.type.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            total_uses=form.total_uses.data,
            used=0,
            user_id=form.user_id.data
        )
        db.session.add(new_pass)
        db.session.commit()
        send_email("Új bérlet", f"Bérlet létrehozva: {new_pass.type}", new_pass.user.email)
        flash("Bérlet sikeresen létrehozva.", "success")
        return redirect(url_for('user.dashboard'))

    return render_template('create_pass.html', form=form)

@admin_bp.route('/delete_pass/<int:pass_id>')
@login_required
def delete_pass(pass_id):
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))

    selected_pass = Pass.query.get_or_404(pass_id)
    db.session.delete(selected_pass)
    db.session.commit()
    flash("Bérlet törölve.", "success")
    return redirect(url_for('user.dashboard'))