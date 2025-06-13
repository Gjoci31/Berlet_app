from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from ..models import Event, EventRegistration, User, db
from ..forms import EventForm


event_bp = Blueprint('events', __name__)


def _get_two_week_range():
    start = datetime.now().date()
    end = start + timedelta(days=13)
    return start, end


@event_bp.route('/events')
@login_required
def events():
    start, end = _get_two_week_range()
    events = (
        Event.query.filter(Event.start_time >= start, Event.start_time <= end)
        .order_by(Event.start_time)
        .all()
    )
    registrations = {
        reg.event_id: reg
        for reg in EventRegistration.query.filter_by(user_id=current_user.id)
    }
    return render_template('events.html', events=events, start=start, end=end, registrations=registrations)


@event_bp.route('/events/signup/<int:event_id>')
@login_required
def signup(event_id):
    event = Event.query.get_or_404(event_id)
    if event.spots_left <= 0:
        flash('Nincs szabad hely.', 'danger')
    elif EventRegistration.query.filter_by(event_id=event_id, user_id=current_user.id).first():
        flash('Már jelentkeztél erre az eseményre.', 'warning')
    else:
        reg = EventRegistration(event_id=event_id, user_id=current_user.id)
        db.session.add(reg)
        db.session.commit()
        flash('Jelentkezés sikeres.', 'success')
    return redirect(url_for('events.events'))


@event_bp.route('/events/unregister/<int:event_id>')
@login_required
def unregister(event_id):
    reg = EventRegistration.query.filter_by(event_id=event_id, user_id=current_user.id).first_or_404()
    db.session.delete(reg)
    db.session.commit()
    flash('Jelentkezés törölve.', 'success')
    return redirect(url_for('events.events'))


@event_bp.route('/admin/events')
@login_required
def admin_events():
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    start, end = _get_two_week_range()
    events = (
        Event.query.filter(Event.start_time >= start, Event.start_time <= end)
        .order_by(Event.start_time)
        .all()
    )
    users = User.query.all()
    return render_template('admin_events.html', events=events, users=users, start=start, end=end)


@event_bp.route('/admin/events/create', methods=['GET', 'POST'])
@login_required
def create_event():
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    form = EventForm()
    if form.validate_on_submit():
        event = Event(
            name=form.name.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            capacity=form.capacity.data,
        )
        db.session.add(event)
        db.session.commit()
        flash('Esemény létrehozva.', 'success')
        return redirect(url_for('events.admin_events'))
    return render_template('create_event.html', form=form)


@event_bp.route('/admin/events/add_user/<int:event_id>', methods=['POST'])
@login_required
def add_user(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    user_id = request.form.get('user_id', type=int)
    event = Event.query.get_or_404(event_id)
    if event.spots_left <= 0:
        flash('Nincs szabad hely.', 'danger')
    elif EventRegistration.query.filter_by(event_id=event_id, user_id=user_id).first():
        flash('A felhasználó már jelentkezett.', 'warning')
    else:
        reg = EventRegistration(event_id=event_id, user_id=user_id)
        db.session.add(reg)
        db.session.commit()
        flash('Felhasználó hozzáadva.', 'success')
    return redirect(url_for('events.admin_events'))
