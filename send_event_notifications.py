"""Send event reminder, pass deduction, and thank you emails."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app import create_app, db
from app.models import EmailSettings, Event, EventRegistration, Pass
from app.email_templates import event_reminder_email, event_thank_you_email, pass_used_email
from app.utils import send_event_email


def _send_event_reminders(now: datetime, settings: EmailSettings | None) -> int:
    if not settings or not settings.event_reminder_enabled:
        return 0

    window_end = now + timedelta(hours=24)
    registrations = (
        EventRegistration.query.join(Event)
        .filter(
            EventRegistration.status == 'active',
            EventRegistration.reminder_sent.is_(False),
            Event.start_time > now,
            Event.start_time <= window_end,
        )
        .all()
    )

    sent = 0
    for registration in registrations:
        event = registration.event
        if not event:
            continue
        if send_event_email(
            'event_reminder',
            'Esemény emlékeztető',
            event_reminder_email(event),
            registration.user.email,
        ):
            registration.reminder_sent = True
            sent += 1
    return sent


def _send_pass_deduction_notifications(now: datetime, settings: EmailSettings | None) -> int:
    if not settings or not settings.pass_used_enabled:
        return 0

    window_start = now - timedelta(hours=36)
    registrations = (
        EventRegistration.query.join(Event)
        .filter(
            Event.end_time <= now,
            Event.end_time >= window_start,
            EventRegistration.pass_usage_id.isnot(None),
            EventRegistration.pass_deduction_notified.is_(False),
            EventRegistration.status.in_(('active', 'late_cancelled')),
        )
        .all()
    )

    sent = 0
    for registration in registrations:
        event = registration.event
        if not event:
            continue
        if not registration.user:
            continue
        associated_pass = Pass.query.get(registration.pass_id)
        if not associated_pass:
            registration.pass_deduction_notified = True
            continue
        if send_event_email(
            'pass_used',
            'Bérlet használat',
            pass_used_email(associated_pass, event),
            registration.user.email,
        ):
            registration.pass_deduction_notified = True
            sent += 1
    return sent


def _send_event_thank_you_notifications(now: datetime, settings: EmailSettings | None) -> int:
    if not settings or not settings.event_thank_you_enabled:
        return 0

    window_start = now - timedelta(hours=36)
    registrations = (
        EventRegistration.query.join(Event)
        .filter(
            Event.end_time <= now,
            Event.end_time >= window_start,
            EventRegistration.pass_usage_id.is_(None),
            EventRegistration.thank_you_sent.is_(False),
            EventRegistration.status == 'active',
        )
        .all()
    )

    sent = 0
    for registration in registrations:
        event = registration.event
        if not event or not registration.user:
            continue
        if send_event_email(
            'event_thank_you',
            'Köszönjük a részvételt',
            event_thank_you_email(registration.user.username, event),
            registration.user.email,
        ):
            registration.thank_you_sent = True
            sent += 1
    return sent


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    with app.app_context():
        now = datetime.utcnow()
        settings = EmailSettings.query.first()
        reminders = _send_event_reminders(now, settings)
        deductions = _send_pass_deduction_notifications(now, settings)
        thank_yous = _send_event_thank_you_notifications(now, settings)
        db.session.commit()
        logging.info(
            "Esemény emlékeztetők kiküldve: %s, levonási értesítők: %s, köszönő üzenetek: %s",
            reminders,
            deductions,
            thank_yous,
        )


if __name__ == '__main__':
    main()
