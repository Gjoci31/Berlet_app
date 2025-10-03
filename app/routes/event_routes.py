import os
from datetime import datetime, timedelta, date

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    current_app,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..models import (
    Event,
    EventRegistration,
    EventWaitlist,
    User,
    Pass,
    PassUsage,
    db,
)
from ..forms import EventForm
from ..utils import send_event_email
from ..email_templates import (
    event_signup_user_email,
    event_signup_admin_email,
    event_unregister_user_email,
    event_unregister_admin_email,
)


event_bp = Blueprint('events', __name__)


def _get_available_pass(user, preferred_pass_id=None):
    """Return the user's first valid pass with remaining uses."""
    today = date.today()
    passes = Pass.query.filter_by(user_id=user.id).all()
    valid = [
        p
        for p in passes
        if p.start_date <= today <= p.end_date and p.used < p.total_uses
    ]
    if preferred_pass_id:
        for p in valid:
            if p.id == preferred_pass_id:
                return p
    if valid:
        valid.sort(key=lambda p: (p.end_date, p.id))
        return valid[0]
    return None


def _handle_pass_usage(selected_pass):
    """Reserve one usage on the given pass and return the usage ID."""
    selected_pass.used += 1
    usage = PassUsage(pass_id=selected_pass.id)
    db.session.add(usage)
    db.session.flush()
    return usage.id


def _uploads_dir() -> str:
    return os.path.join(current_app.root_path, 'static', 'uploads')


def _save_event_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    if not filename:
        return None
    upload_dir = _uploads_dir()
    os.makedirs(upload_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    name, ext = os.path.splitext(filename)
    final_name = f"{name}_{timestamp}{ext}"
    path = os.path.join(upload_dir, final_name)
    file_storage.save(path)
    return os.path.join('uploads', final_name)


def _cancel_registration(registration, force_late=None):
    """Cancel a registration and handle pass adjustments."""
    event = registration.event
    now = datetime.now()
    late_cancel = (
        force_late
        if force_late is not None
        else (event.start_time - now <= timedelta(hours=48))
    )
    if registration.registration_type == 'pass' and registration.pass_id:
        selected_pass = Pass.query.get(registration.pass_id)
        if not late_cancel:
            if selected_pass and selected_pass.used > 0:
                selected_pass.used -= 1
            if registration.pass_usage_id:
                usage = PassUsage.query.get(registration.pass_usage_id)
                if usage:
                    db.session.delete(usage)
            registration.pass_usage_id = None
        else:
            registration.is_late_cancel = True
    registration.status = 'late_cancelled' if late_cancel else 'cancelled'
    registration.cancelled_at = datetime.utcnow()
    db.session.commit()
    return late_cancel


def _promote_waitlist_entry(entry, event=None, remove_on_fail=False):
    """Promote a single waitlist entry to an active registration."""
    event = event or entry.event
    if not event or event.status != 'upcoming' or event.spots_left <= 0:
        return False

    if EventRegistration.query.filter_by(
        event_id=event.id, user_id=entry.user_id, status='active'
    ).first():
        if remove_on_fail:
            db.session.delete(entry)
            db.session.commit()
        return False

    user = entry.user
    selected_pass = None
    if entry.registration_type == 'pass':
        selected_pass = _get_available_pass(user, entry.pass_id)
        if not selected_pass:
            if remove_on_fail:
                db.session.delete(entry)
                db.session.commit()
            return False

    registration = EventRegistration(
        event_id=event.id,
        user_id=user.id,
        registration_type=entry.registration_type,
        waitlist_promoted=True,
    )
    if selected_pass:
        registration.pass_id = selected_pass.id
        registration.pass_usage_id = _handle_pass_usage(selected_pass)
    db.session.add(registration)
    db.session.delete(entry)
    db.session.commit()

    send_event_email(
        'event_signup_user',
        'Esemény jelentkezés',
        event_signup_user_email(user.username, event),
        user.email,
    )
    return True


def _promote_waitlist(event_id: int):
    """Move the first waitlisted users into the event if space allows."""
    event = Event.query.get(event_id)
    if not event:
        return

    if event.status != 'upcoming':
        return

    while event.spots_left > 0:
        entry = (
            EventWaitlist.query.filter_by(event_id=event.id)
            .order_by(EventWaitlist.created_at)
            .first()
        )
        if not entry:
            break
        _promote_waitlist_entry(entry, event, remove_on_fail=True)
        event = Event.query.get(event.id)


@event_bp.route('/events')
@login_required
def events():
    events = Event.query.order_by(Event.start_time).all()
    active_registrations = {
        reg.event_id: reg
        for reg in EventRegistration.query.filter_by(
            user_id=current_user.id, status='active'
        )
    }
    latest_registrations = {}
    for reg in (
        EventRegistration.query.filter_by(user_id=current_user.id)
        .order_by(EventRegistration.created_at.desc())
        .all()
    ):
        if reg.event_id not in latest_registrations:
            latest_registrations[reg.event_id] = reg
    waitlist_map = {
        entry.event_id: entry
        for entry in EventWaitlist.query.filter_by(user_id=current_user.id).all()
    }
    has_active_pass = _get_available_pass(current_user) is not None
    return render_template(
        'events.html',
        events=events,
        active_registrations=active_registrations,
        latest_registrations=latest_registrations,
        waitlist_map=waitlist_map,
        has_active_pass=has_active_pass,
    )


@event_bp.route('/events/signup/<int:event_id>', methods=['POST'])
@login_required
def signup(event_id):
    event = Event.query.get_or_404(event_id)
    now = datetime.utcnow()
    if event.start_time <= now:
        flash('Ez az esemény már elkezdődött vagy lezajlott.', 'warning')
        return redirect(url_for('events.events'))

    if EventRegistration.query.filter_by(
        event_id=event_id, user_id=current_user.id, status='active'
    ).first():
        flash('Már jelentkeztél erre az eseményre.', 'warning')
        return redirect(url_for('events.events'))

    if event.spots_left <= 0:
        flash('Az esemény teltházas, csatlakozz a várólistához.', 'warning')
        return redirect(url_for('events.events'))

    registration_type = request.form.get('registration_type', 'single')
    preferred_pass_id = request.form.get('pass_id', type=int)
    selected_pass = None
    if registration_type == 'pass':
        selected_pass = _get_available_pass(current_user, preferred_pass_id)
        if not selected_pass:
            flash('Nincs elérhető bérleted a jelentkezéshez.', 'danger')
            return redirect(url_for('events.events'))

    waitlist_entry = EventWaitlist.query.filter_by(
        event_id=event_id, user_id=current_user.id
    ).first()
    if waitlist_entry:
        db.session.delete(waitlist_entry)

    registration = EventRegistration(
        event_id=event_id,
        user_id=current_user.id,
        registration_type='pass' if selected_pass else 'single',
    )
    if selected_pass:
        registration.pass_id = selected_pass.id
        registration.pass_usage_id = _handle_pass_usage(selected_pass)
    db.session.add(registration)
    db.session.commit()

    send_event_email(
        'event_signup_user',
        'Esemény jelentkezés',
        event_signup_user_email(current_user.username, event),
        current_user.email,
    )
    flash('Jelentkezés sikeres.', 'success')
    return redirect(url_for('events.events'))


@event_bp.route('/events/unregister/<int:event_id>', methods=['POST'])
@login_required
def unregister(event_id):
    registration = EventRegistration.query.filter_by(
        event_id=event_id, user_id=current_user.id, status='active'
    ).first()
    waitlist_entry = EventWaitlist.query.filter_by(
        event_id=event_id, user_id=current_user.id
    ).first()

    if not registration and not waitlist_entry:
        flash('Nem találtunk aktív jelentkezést.', 'warning')
        return redirect(url_for('events.events'))

    if registration:
        late_cancel = _cancel_registration(registration)
        event = Event.query.get(event_id)
        send_event_email(
            'event_unregister_user',
            'Esemény leiratkozás',
            event_unregister_user_email(current_user.username, event),
            current_user.email,
        )
        if late_cancel and registration.registration_type == 'pass':
            flash('48 órán belül mondtad le, az alkalom levonva marad.', 'warning')
        else:
            flash('Jelentkezés törölve.', 'success')
        _promote_waitlist(event_id)
    else:
        db.session.delete(waitlist_entry)
        db.session.commit()
        flash('Eltávolítva a várólistáról.', 'success')

    return redirect(url_for('events.events'))


@event_bp.route('/events/waitlist/<int:event_id>', methods=['POST'])
@login_required
def join_waitlist(event_id):
    event = Event.query.get_or_404(event_id)

    now = datetime.utcnow()
    if event.start_time <= now:
        flash('Ez az esemény már elkezdődött vagy lezajlott.', 'warning')
        return redirect(url_for('events.events'))

    if EventRegistration.query.filter_by(
        event_id=event_id, user_id=current_user.id, status='active'
    ).first():
        flash('Már jelentkeztél erre az eseményre.', 'warning')
        return redirect(url_for('events.events'))

    if event.spots_left > 0:
        flash('Még van szabad hely, jelentkezz közvetlenül.', 'info')
        return redirect(url_for('events.events'))

    if EventWaitlist.query.filter_by(
        event_id=event_id, user_id=current_user.id
    ).first():
        flash('Már szerepelsz a várólistán.', 'warning')
        return redirect(url_for('events.events'))

    registration_type = request.form.get('registration_type', 'single')
    preferred_pass_id = request.form.get('pass_id', type=int)
    entry_kwargs = {
        'event_id': event_id,
        'user_id': current_user.id,
        'registration_type': 'single',
    }
    if registration_type == 'pass':
        selected_pass = _get_available_pass(current_user, preferred_pass_id)
        if not selected_pass:
            flash('Nincs elérhető bérleted a várólistához.', 'danger')
            return redirect(url_for('events.events'))
        entry_kwargs['registration_type'] = 'pass'
        entry_kwargs['pass_id'] = selected_pass.id

    waitlist_entry = EventWaitlist(**entry_kwargs)
    db.session.add(waitlist_entry)
    db.session.commit()
    flash('Feliratkoztál a várólistára.', 'success')
    return redirect(url_for('events.events'))


@event_bp.route('/events/waitlist/remove/<int:event_id>', methods=['POST'])
@login_required
def leave_waitlist(event_id):
    entry = EventWaitlist.query.filter_by(
        event_id=event_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash('Eltávolítva a várólistáról.', 'success')
    return redirect(url_for('events.events'))


@event_bp.route('/admin/events')
@login_required
def admin_events():
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    events = Event.query.order_by(Event.start_time).all()
    users = User.query.all()
    return render_template('admin_events.html', events=events, users=users)


@event_bp.route('/admin/events/create', methods=['GET', 'POST'])
@login_required
def create_event():
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    form = EventForm()
    if form.validate_on_submit():
        start_dt = datetime.combine(form.date.data, form.start_time.data)
        end_dt = datetime.combine(form.date.data, form.end_time.data)
        event = Event(
            name=form.name.data,
            start_time=start_dt,
            end_time=end_dt,
            capacity=form.capacity.data,
            color=form.color.data,
            price=form.price.data if form.price.data is not None else None,
        )
        image_path = _save_event_image(form.image.data)
        if image_path:
            event.image_path = image_path
        db.session.add(event)
        db.session.commit()
        flash('Esemény létrehozva.', 'success')
        return redirect(url_for('events.admin_events'))
    return render_template('create_event.html', form=form)


@event_bp.route('/admin/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))

    event = Event.query.get_or_404(event_id)
    form = EventForm(obj=event)

    if request.method == 'GET':
        form.date.data = event.start_time.date()
        form.start_time.data = event.start_time.time()
        form.end_time.data = event.end_time.time()
        if event.price is not None:
            form.price.data = float(event.price)

    if form.validate_on_submit():
        event.name = form.name.data
        event.start_time = datetime.combine(form.date.data, form.start_time.data)
        event.end_time = datetime.combine(form.date.data, form.end_time.data)
        event.capacity = form.capacity.data
        event.color = form.color.data
        event.price = form.price.data if form.price.data is not None else None
        image_path = _save_event_image(form.image.data)
        if image_path:
            event.image_path = image_path
        db.session.commit()
        flash('Esemény frissítve.', 'success')
        return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    return render_template('edit_event.html', form=form, event=event)


@event_bp.route('/admin/events/add_user/<int:event_id>', methods=['POST'])
@login_required
def add_user(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    user_id = request.form.get('user_id', type=int)
    registration_type = request.form.get('registration_type', 'single')
    user = User.query.get_or_404(user_id)
    event = Event.query.get_or_404(event_id)

    if event.spots_left <= 0:
        flash('Nincs szabad hely.', 'danger')
        return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    if EventRegistration.query.filter_by(
        event_id=event_id, user_id=user_id, status='active'
    ).first():
        flash('A felhasználó már jelentkezett.', 'warning')
        return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    selected_pass = None
    if registration_type == 'pass':
        selected_pass = _get_available_pass(user)
        if not selected_pass:
            flash('A felhasználónak nincs aktív bérlete.', 'danger')
            return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    registration = EventRegistration(
        event_id=event_id,
        user_id=user_id,
        registration_type='pass' if selected_pass else 'single',
    )
    if selected_pass:
        registration.pass_id = selected_pass.id
        registration.pass_usage_id = _handle_pass_usage(selected_pass)
    db.session.add(registration)
    db.session.commit()

    send_event_email(
        'event_signup_admin',
        'Esemény jelentkezés',
        event_signup_admin_email(user.username, event),
        user.email,
    )
    flash('Felhasználó hozzáadva.', 'success')
    return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))


@event_bp.route('/admin/events/remove_user/<int:event_id>/<int:user_id>', methods=['POST'])
@login_required
def remove_user(event_id, user_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    registration = EventRegistration.query.filter_by(
        event_id=event_id, user_id=user_id, status='active'
    ).first_or_404()
    _cancel_registration(registration, force_late=False)
    event = registration.event
    user = registration.user
    send_event_email(
        'event_unregister_admin',
        'Esemény leiratkozás',
        event_unregister_admin_email(user.username, event),
        user.email,
    )
    flash('Felhasználó eltávolítva.', 'success')
    _promote_waitlist(event_id)
    return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))


@event_bp.route('/admin/events/waitlist/promote/<int:event_id>/<int:entry_id>', methods=['POST'])
@login_required
def promote_waitlist(event_id, entry_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))

    entry = EventWaitlist.query.filter_by(id=entry_id, event_id=event_id).first_or_404()
    event = Event.query.get_or_404(event_id)

    if _promote_waitlist_entry(entry, event, remove_on_fail=False):
        flash('Felhasználó átsorolva az eseményre.', 'success')
    else:
        flash('Az átsorolás nem sikerült. Ellenőrizd a bérletet vagy a férőhelyeket.', 'danger')
    return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))


@event_bp.route('/admin/events/waitlist/remove/<int:event_id>/<int:entry_id>', methods=['POST'])
@login_required
def remove_waitlist_entry(event_id, entry_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    entry = EventWaitlist.query.filter_by(id=entry_id, event_id=event_id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash('Várólista jelentkezés törölve.', 'success')
    return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))


@event_bp.route('/admin/events/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    event = Event.query.get_or_404(event_id)
    for registration in list(event.registrations):
        if registration.status == 'active':
            _cancel_registration(registration, force_late=False)
    EventWaitlist.query.filter_by(event_id=event_id).delete(synchronize_session=False)
    db.session.delete(event)
    db.session.commit()
    flash('Esemény törölve.', 'success')
    return redirect(url_for('events.admin_events'))
