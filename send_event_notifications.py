"""Send event reminder, pass deduction, and thank you emails."""

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
        now = datetime.utcnow()
        settings = EmailSettings.query.first()
        reminders = send_event_reminders(now, settings)
        deductions = send_pass_deduction_notifications(now, settings)
        thank_yous = send_event_thank_you_notifications(now, settings)
        db.session.commit()
        logging.info(
            "Esemény emlékeztetők kiküldve: %s, levonási értesítők: %s, köszönő üzenetek: %s",
            reminders,
            deductions,
            thank_yous,
        )


if __name__ == '__main__':
    main()
