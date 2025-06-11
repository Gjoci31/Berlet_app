from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..models import Pass, User, db
from ..forms import PassForm, UserForm
from ..utils import send_email
from ..email_templates import pass_created_email, pass_deleted_email, pass_used_email
from datetime import date

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
            comment=form.comment.data,
            user_id=form.user_id.data
        )
        db.session.add(new_pass)
        db.session.commit()
        send_email(
            "Új bérlet", 
            pass_created_email(new_pass.user.username, new_pass.type, new_pass.start_date, new_pass.end_date, new_pass.total_uses),
            new_pass.user.email
        )
        flash("Bérlet sikeresen létrehozva.", "success")
        return redirect(url_for('user.dashboard'))

    return render_template('create_pass.html', form=form)


@admin_bp.route('/extend_pass/<int:pass_id>', methods=['GET', 'POST'])
@login_required
def extend_pass(pass_id):
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))

    p = Pass.query.get_or_404(pass_id)
    form = PassForm(obj=p)
    users = User.query.all()
    form.user_id.choices = [(u.id, u.username) for u in users]
    if form.validate_on_submit():
        p.type = form.type.data
        p.start_date = form.start_date.data
        p.end_date = form.end_date.data
        p.total_uses = form.total_uses.data
        p.comment = form.comment.data
        p.user_id = form.user_id.data
        db.session.commit()
        send_email(
            "Bérlet hosszabbítva",
            pass_created_email(p.user.username, p.type, p.start_date, p.end_date, p.total_uses),
            p.user.email,
        )
        flash("Bérlet módosítva.", "success")
        return redirect(url_for('admin.verify_pass', pass_id=p.id))

    return render_template('extend_pass.html', form=form)

@admin_bp.route('/delete_pass/<int:pass_id>')
@login_required
def delete_pass(pass_id):
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))

    selected_pass = Pass.query.get_or_404(pass_id)
    db.session.delete(selected_pass)
    db.session.commit()
    send_email(
        "Bérlet törölve",
        pass_deleted_email(selected_pass.user.username, selected_pass.type, selected_pass.start_date, selected_pass.end_date, selected_pass.used),
        selected_pass.user.email,
    )
    flash("Bérlet törölve.", "success")
    return redirect(url_for('user.dashboard'))


@admin_bp.route('/verify_pass/<int:pass_id>')
@login_required
def verify_pass(pass_id):
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))

    p = Pass.query.get_or_404(pass_id)
    today = date.today()
    return render_template('verify_pass.html', p=p, today=today)


@admin_bp.route('/use_pass/<int:pass_id>')
@login_required
def use_pass(pass_id):
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))

    p = Pass.query.get_or_404(pass_id)
    if p.used < p.total_uses and p.end_date >= date.today():
        p.used += 1
        db.session.commit()
        remaining = p.total_uses - p.used
        send_email(
            "Bérlet használat",
            pass_used_email(p.user.username, p.type, remaining),
            p.user.email,
        )
        flash("Alkalom hozzáadva.", "success")
    else:
        flash("A bérlet nem használható.", "danger")
    return redirect(url_for('admin.verify_pass', pass_id=pass_id))


@admin_bp.route('/undo_use/<int:pass_id>')
@login_required
def undo_use(pass_id):
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))

    p = Pass.query.get_or_404(pass_id)
    if p.used > 0:
        p.used -= 1
        db.session.commit()
        flash("Felhasználás visszavonva.", "success")
    return redirect(url_for('admin.verify_pass', pass_id=pass_id))


@admin_bp.route('/users')
@login_required
def users():
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))
    users = User.query.all()
    return render_template('users.html', users=users)


@admin_bp.route('/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))

    form = UserForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Felhasználó létrehozva.", "success")
        return redirect(url_for('admin.users'))

    return render_template('create_user.html', form=form)


@admin_bp.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('user.dashboard'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("Felhasználó törölve.", "success")
    return redirect(url_for('admin.users'))
