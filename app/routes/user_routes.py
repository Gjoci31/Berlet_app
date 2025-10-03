from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from ..models import Pass, PassRequest, User, db
from ..forms import PurchasePassForm
from ..utils import send_email
from ..email_templates import pass_request_admin_email

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        passes = Pass.query.all()
        pending_requests = (
            PassRequest.query.filter_by(status='pending')
            .order_by(PassRequest.created_at.asc())
            .all()
        )
        return render_template(
            'dashboard.html',
            passes=passes,
            user=current_user,
            pass_requests=[],
            pending_requests=pending_requests,
        )

    passes = Pass.query.filter_by(user_id=current_user.id).all()
    pass_requests = (
        PassRequest.query.filter_by(user_id=current_user.id)
        .order_by(PassRequest.created_at.desc())
        .all()
    )
    return render_template(
        'dashboard.html',
        passes=passes,
        user=current_user,
        pass_requests=pass_requests,
        pending_requests=[],
    )


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
        existing_pending = PassRequest.query.filter_by(
            user_id=current_user.id, status='pending'
        ).first()
        if existing_pending:
            flash('Már van függő bérlet igénylésed. Várd meg, míg az admin feldolgozza.', 'warning')
            return redirect(url_for('user.dashboard'))

        uses = int(form.pass_type.data)
        pass_request = PassRequest(user_id=current_user.id, requested_uses=uses)
        db.session.add(pass_request)
        db.session.commit()
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            send_email(
                'Új bérlet igénylés',
                pass_request_admin_email(current_user, pass_request),
                admin.email,
            )
        flash('Bérlet igénylésed rögzítettük. Az admin felveszi veled a kapcsolatot a fizetéshez.', 'success')
        return redirect(url_for('user.dashboard'))
    return render_template('purchase_pass.html', form=form)
