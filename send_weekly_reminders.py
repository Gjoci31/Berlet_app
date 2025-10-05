"""Send reminder emails for events starting within the next 24 hours."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app import create_app, db
from app.email_templates import event_reminder_email
from app.models import EmailSettings, Event, EventRegistration
from app.utils import send_event_email


def _fetch_pending_registrations(now: datetime) -> list[EventRegistration]:
    """Return registrations that require a reminder email."""

    window_end = now + timedelta(hours=24)
    return (
        EventRegistration.query.join(Event)
        .filter(
            EventRegistration.status == 'active',
            EventRegistration.reminder_sent.is_(False),
            Event.start_time > now,
            Event.start_time <= window_end,
        )
        .all()
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    with app.app_context():
        settings = EmailSettings.query.first()
        if not settings or not settings.event_reminder_enabled:
            logging.info(
                "Esemény emlékeztető funkció letiltva, nincs kiküldendő e-mail."
            )
            return

        now = datetime.utcnow()
        registrations = _fetch_pending_registrations(now)
        if not registrations:
            logging.info("Nincs kiküldendő esemény emlékeztető e-mail.")
            return

        sent = 0
        for registration in registrations:
            event = registration.event
            user = registration.user
            if not event or not user or not user.email:
                continue

            if send_event_email(
                'event_reminder',
                'Esemény emlékeztető',
                event_reminder_email(event),
                user.email,
            ):
                registration.reminder_sent = True
                sent += 1

        db.session.commit()
        logging.info(
            "Esemény emlékeztetők kiküldve: %s/%s", sent, len(registrations)
        )


if __name__ == "__main__":
    main()
