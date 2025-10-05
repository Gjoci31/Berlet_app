"""Utility functions for sending scheduled event-related emails."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.email_templates import (
    event_reminder_email,
    event_thank_you_email,
    pass_used_email,
)
from app.models import EmailSettings, Event, EventRegistration, Pass
from app.utils import send_event_email


def send_event_reminders(now: datetime, settings: EmailSettings | None) -> int:
    """Send reminder e-mails for events starting within the next 24 hours."""

    if not settings:
        logging.info("Nincsenek e-mail beállítások, emlékeztetők kihagyva.")
        return 0

    if not settings.event_reminder_enabled:
        logging.info(
            "Esemény emlékeztető funkció letiltva, nincs kiküldendő e-mail."
        )
        return 0

    window_end = now + timedelta(hours=24)
    registrations = (
        EventRegistration.query.join(Event)
        .filter(
            EventRegistration.status == "active",
            EventRegistration.reminder_sent.is_(False),
            Event.start_time > now,
            Event.start_time <= window_end,
        )
        .all()
    )

    if not registrations:
        logging.info("Nincs kiküldendő esemény emlékeztető e-mail.")
        return 0

    sent = 0
    for registration in registrations:
        event = registration.event
        user = registration.user
        if not event or not user or not user.email:
            continue

        if send_event_email(
            "event_reminder",
            "Esemény emlékeztető",
            event_reminder_email(event),
            user.email,
        ):
            registration.reminder_sent = True
            sent += 1

    return sent


def send_pass_deduction_notifications(
    now: datetime, settings: EmailSettings | None
) -> int:
    """Notify users about pass deductions for events that ended recently."""

    if not settings:
        logging.info("Nincsenek e-mail beállítások, bérlet értesítők kihagyva.")
        return 0

    if not settings.pass_used_enabled:
        logging.info("Bérlet levonási értesítők kiküldése letiltva.")
        return 0

    window_start = now - timedelta(hours=36)
    registrations = (
        EventRegistration.query.join(Event)
        .filter(
            Event.end_time <= now,
            Event.end_time >= window_start,
            EventRegistration.pass_usage_id.isnot(None),
            EventRegistration.pass_deduction_notified.is_(False),
            EventRegistration.status.in_(("active", "late_cancelled")),
        )
        .all()
    )

    sent = 0
    for registration in registrations:
        event = registration.event
        user = registration.user
        if not event or not user or not user.email:
            continue

        associated_pass = Pass.query.get(registration.pass_id)
        if not associated_pass:
            registration.pass_deduction_notified = True
            continue

        if send_event_email(
            "pass_used",
            "Bérlet használat",
            pass_used_email(associated_pass, event),
            user.email,
        ):
            registration.pass_deduction_notified = True
            sent += 1

    return sent


def send_event_thank_you_notifications(
    now: datetime, settings: EmailSettings | None
) -> int:
    """Send thank-you e-mails to attendees without pass usage."""

    if not settings:
        logging.info("Nincsenek e-mail beállítások, köszönő üzenetek kihagyva.")
        return 0

    if not settings.event_thank_you_enabled:
        logging.info("Köszönő e-mailek kiküldése letiltva.")
        return 0

    window_start = now - timedelta(hours=36)
    registrations = (
        EventRegistration.query.join(Event)
        .filter(
            Event.end_time <= now,
            Event.end_time >= window_start,
            EventRegistration.pass_usage_id.is_(None),
            EventRegistration.thank_you_sent.is_(False),
            EventRegistration.status == "active",
        )
        .all()
    )

    sent = 0
    for registration in registrations:
        event = registration.event
        user = registration.user
        if not event or not user or not user.email:
            continue

        if send_event_email(
            "event_thank_you",
            "Köszönjük a részvételt",
            event_thank_you_email(user.username, event),
            user.email,
        ):
            registration.thank_you_sent = True
            sent += 1

    return sent
