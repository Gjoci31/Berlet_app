"""Run scheduled event-related email tasks."""

from __future__ import annotations

import logging
from datetime import datetime

from app import create_app, db
from app.models import EmailSettings
from app.notification_tasks import (
    send_event_reminders,
    send_event_thank_you_notifications,
    send_pass_deduction_notifications,
)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    with app.app_context():
        settings = EmailSettings.query.first()
        now = datetime.utcnow()
        reminders = send_event_reminders(now, settings)
        pass_notifications = send_pass_deduction_notifications(now, settings)
        thank_yous = send_event_thank_you_notifications(now, settings)
        db.session.commit()
        logging.info(
            "Összegzés - emlékeztetők: %s, bérlet levonások: %s, köszönő üzenetek: %s",
            reminders,
            pass_notifications,
            thank_yous,
        )


if __name__ == "__main__":
    main()
