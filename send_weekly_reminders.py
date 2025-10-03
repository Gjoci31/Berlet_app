"""Legacy entry point for the removed weekly reminder feature.

The original application scheduled this module to run periodically to send
emails.  The customer no longer needs weekly reminders, so the script simply
logs a short notice instead of touching the database or sending mail.
"""

import logging


def main() -> None:
    logging.info("Weekly reminder funkció letiltva, nincs teendő.")


if __name__ == "__main__":
    main()
