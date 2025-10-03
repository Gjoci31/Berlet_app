from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from .. import db
from ..forms import PurchasePassForm
from ..models import Pass, PassRequest, User
from ..email_templates import pass_request_admin_email
from ..utils import send_email


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
            flash('Már van feldolgozás alatt lévő bérlet igénylésed.', 'warning')
            return redirect(url_for('user.dashboard'))

        pass_request = PassRequest(
            user_id=current_user.id,
            requested_uses=int(form.pass_type.data),
        )
        db.session.add(pass_request)
        db.session.commit()

        admins = User.query.filter_by(role='admin').all()
        html = pass_request_admin_email(current_user, pass_request)
        for admin in admins:
            send_email('Új bérlet igénylés', html, admin.email)

        flash('Bérlet igénylésed rögzítettük.', 'success')
        return redirect(url_for('user.dashboard'))
    return render_template('purchase_pass.html', form=form)
