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
from ..utils import send_email, send_event_email
from ..email_templates import (
    event_signup_user_email,
    event_signup_admin_email,
    event_unregister_user_email,
    event_unregister_admin_email,
    event_waitlist_join_email,
    event_waitlist_removed_email,
)


event_bp = Blueprint('events', __name__)


def _get_available_pass(user, preferred_pass_id=None):
    """Return the user's first valid pass with remaining uses."""
    today = date.today()
    passes = Pass.query.filter_by(user_id=user.id).all()
    valid = [
        p
        for p in passes
        if p.start_date <= today <= p.end_date and _pass_has_bookable_use(p)
    ]
    if preferred_pass_id:
        for p in valid:
            if p.id == preferred_pass_id:
                return p
    if valid:
        valid.sort(key=lambda p: (p.end_date, p.id))
        return valid[0]
    return None


def _reserved_uses_for_pass(pass_id: int) -> int:
    """Return how many upcoming active registrations reserve this pass."""
    return (
        EventRegistration.query.join(Event)
        .filter(
            EventRegistration.pass_id == pass_id,
            EventRegistration.status == 'active',
            EventRegistration.pass_usage_id.is_(None),
            Event.start_time > datetime.utcnow(),
        )
        .count()
    )


def _pass_has_bookable_use(selected_pass) -> bool:
    """Return whether the pass has at least one use left to reserve."""
    reserved = _reserved_uses_for_pass(selected_pass.id)
    remaining = selected_pass.total_uses - selected_pass.used - reserved
    return remaining > 0


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
        else (event.start_time - now <= timedelta(minutes=1))
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
    if user.is_blacklisted:
        if remove_on_fail:
            db.session.delete(entry)
            db.session.commit()
        return False
    selected_pass = None
    registration_type = entry.registration_type
    if event.is_final_event:
        registration_type = 'single'
    elif registration_type == 'pass':
        selected_pass = _get_available_pass(user, entry.pass_id)
        if not selected_pass:
            if remove_on_fail:
                db.session.delete(entry)
                db.session.commit()
            return False

    registration = EventRegistration(
        event_id=event.id,
        user_id=user.id,
        registration_type=registration_type,
        waitlist_promoted=True,
    )
    if selected_pass:
        registration.pass_id = selected_pass.id
    db.session.add(registration)
    db.session.delete(entry)
    db.session.commit()

    send_event_email(
        'event_signup_user',
        'Esemény jelentkezés',
        event_signup_user_email(user.username, event, from_waitlist=True),
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
        user_blacklisted=current_user.is_blacklisted,
    )


@event_bp.route('/events/signup/<int:event_id>', methods=['POST'])
@login_required
def signup(event_id):
    event = Event.query.get_or_404(event_id)
    now = datetime.utcnow()
    if current_user.is_blacklisted:
        flash('Nem jelentkezhetsz eseményekre, mert feketelistán vagy.', 'danger')
        return redirect(url_for('events.events'))
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
    if event.is_final_event and registration_type == 'pass':
        flash('Ez a záró esemény, csak alkalmi jelentkezés engedélyezett.', 'warning')
        return redirect(url_for('events.events'))
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
    event = Event.query.get_or_404(event_id)

    registration = EventRegistration.query.filter_by(
        event_id=event_id, user_id=current_user.id, status='active'
    ).first()
    waitlist_entry = EventWaitlist.query.filter_by(
        event_id=event_id, user_id=current_user.id
    ).first()

    if not registration and not waitlist_entry:
        flash('Nem találtunk aktív jelentkezést.', 'warning')
        return redirect(url_for('events.events'))

    now = datetime.utcnow()
    if event.start_time <= now:
        flash(
            'Ez az esemény már elkezdődött vagy lezajlott, módosítás nem lehetséges.',
            'warning',
        )
        return redirect(url_for('events.events'))
    if registration and event.is_unregister_locked:
        flash(
            'A lejelentkezési határidő lejárt ennél az eseménynél.',
            'warning',
        )
        return redirect(url_for('events.events'))

    if registration:
        _cancel_registration(registration, force_late=False)
        used_pass = registration.registration_type == 'pass'
        send_event_email(
            'event_unregister_user',
            'Esemény leiratkozás',
            event_unregister_user_email(
                current_user.username,
                event,
                used_pass=used_pass,
                late_cancel=False,
                deduction_kept=False,
            ),
            current_user.email,
        )
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
    if current_user.is_blacklisted:
        flash('Nem csatlakozhatsz a várólistára, mert feketelistán vagy.', 'danger')
        return redirect(url_for('events.events'))
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
    if event.is_final_event and registration_type == 'pass':
        flash('Ez a záró esemény, csak alkalmi jelentkezés engedélyezett.', 'warning')
        return redirect(url_for('events.events'))
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
    send_email(
        'Várólista jelentkezés',
        event_waitlist_join_email(current_user.username, event),
        current_user.email,
    )
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
            unregister_deadline_minutes=form.unregister_deadline_minutes.data or 0,
            color=form.color.data,
            price=form.price.data if form.price.data is not None else None,
            is_final_event=form.is_final_event.data,
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
        event.unregister_deadline_minutes = form.unregister_deadline_minutes.data or 0
        event.color = form.color.data
        event.price = form.price.data if form.price.data is not None else None
        event.is_final_event = form.is_final_event.data
        image_path = _save_event_image(form.image.data)
        if image_path:
            event.image_path = image_path
        db.session.commit()
        flash('Esemény frissítve.', 'success')
        return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    return render_template('edit_event.html', form=form, event=event)


@event_bp.route('/admin/events/<int:event_id>/toggle_final', methods=['POST'])
@login_required
def toggle_final_event(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))

    event = Event.query.get_or_404(event_id)
    event.is_final_event = not event.is_final_event
    db.session.commit()
    if event.is_final_event:
        flash('Az esemény záró programként lett megjelölve. Bérlet nem használható.', 'success')
    else:
        flash('Az esemény már nem záró program, újra használható bérlet.', 'success')
    return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))


@event_bp.route('/admin/events/add_user/<int:event_id>', methods=['POST'])
@login_required
def add_user(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    user_id = request.form.get('user_id', type=int)
    registration_type = request.form.get('registration_type', 'single')
    user = User.query.get_or_404(user_id)
    event = Event.query.get_or_404(event_id)

    if user.is_blacklisted:
        flash('A felhasználó feketelistán van, nem vehet részt az eseményen.', 'danger')
        return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    if EventRegistration.query.filter_by(
        event_id=event_id, user_id=user_id, status='active'
    ).first():
        flash('A felhasználó már jelentkezett.', 'warning')
        return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    waitlist_entry = EventWaitlist.query.filter_by(
        event_id=event_id, user_id=user_id
    ).first()

    selected_pass = None
    if registration_type == 'pass':
        if event.is_final_event:
            flash('Ez a záró esemény, csak alkalmi jelentkezés engedélyezett.', 'warning')
            return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))
        selected_pass = _get_available_pass(user)
        if not selected_pass:
            flash('A felhasználónak nincs aktív bérlete.', 'danger')
            return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    if event.spots_left <= 0:
        if waitlist_entry:
            flash('A felhasználó már a várólistán van.', 'warning')
        else:
            entry_kwargs = {
                'event_id': event_id,
                'user_id': user_id,
                'registration_type': 'pass' if selected_pass else 'single',
            }
            if selected_pass:
                entry_kwargs['pass_id'] = selected_pass.id
            waitlist_entry = EventWaitlist(**entry_kwargs)
            db.session.add(waitlist_entry)
            db.session.commit()
            send_email(
                'Várólista jelentkezés',
                event_waitlist_join_email(user.username, event),
                user.email,
            )
            flash('Az esemény teltházas, a felhasználó a várólistára került.', 'info')
        return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    if waitlist_entry:
        db.session.delete(waitlist_entry)

    registration = EventRegistration(
        event_id=event_id,
        user_id=user_id,
        registration_type='pass' if selected_pass else 'single',
    )
    if selected_pass:
        registration.pass_id = selected_pass.id
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

    first_entry = (
        EventWaitlist.query.filter_by(event_id=event_id)
        .order_by(EventWaitlist.created_at)
        .first()
    )

    if not first_entry or first_entry.id == entry.id:
        flash('A felhasználó már a várólista elején van.', 'info')
        return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))

    earliest_time = first_entry.created_at or datetime.utcnow()
    entry.created_at = earliest_time - timedelta(seconds=1)
    db.session.commit()

    flash('Felhasználó a várólista elejére került.', 'success')
    return redirect(url_for('events.admin_events', _anchor=f'event-{event_id}'))


@event_bp.route('/admin/events/waitlist/remove/<int:event_id>/<int:entry_id>', methods=['POST'])
@login_required
def remove_waitlist_entry(event_id, entry_id):
    if current_user.role != 'admin':
        return redirect(url_for('events.events'))
    entry = EventWaitlist.query.filter_by(id=entry_id, event_id=event_id).first_or_404()
    event = entry.event
    user = entry.user
    db.session.delete(entry)
    db.session.commit()
    send_email(
        'Várólista eltávolítás',
        event_waitlist_removed_email(user.username, event),
        user.email,
    )
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
