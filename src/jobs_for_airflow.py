import sys
import io
import logging
import pandas as pd

from datetime import datetime
from streamlit.web import cli as stcli
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler

from utils.database import DatabaseClient
from utils.sftp import SFTPClient
from delta import DeltaClient
from ms_graph import MSGraphClient
from utils.config import DB_HOST, DB_USER, DB_PASS, DB_NAME, DB_SCHEMA, SFTP_HOST, SFTP_USER, SFTP_PASS, AD_DB_SCHEMA
from utils.logging import set_logging_configuration

# Set up logging configuration
set_logging_configuration()

logger = logging.getLogger(__name__)

sched = BackgroundScheduler()
db_client = DatabaseClient(db_type="postgresql", database=DB_NAME, username=DB_USER, password=DB_PASS, host=DB_HOST)
sftp_client = SFTPClient(host=SFTP_HOST, username=SFTP_USER, password=SFTP_PASS)
delta_client = DeltaClient()
ms_graph_client = MSGraphClient()


with db_client.get_connection() as conn:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
    conn.commit()


def clean():
    with db_client.get_connection() as conn:
        check_column_query = f"""
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = '{DB_SCHEMA}'
            AND table_name = 'person'
            AND column_name = 'isystem'
        """
        column_exists = conn.execute(text(check_column_query)).fetchone()
        if not column_exists:
            alter_query = f"""
            ALTER TABLE {DB_SCHEMA}.person
            ADD COLUMN isystem BOOLEAN DEFAULT FALSE
            """
            conn.execute(text(alter_query))
            conn.commit()

        # Get all emails and omraade from person table
        email_query = f"SELECT email, omraade FROM {DB_SCHEMA}.person WHERE email IS NOT NULL"
        results = conn.execute(text(email_query)).mappings().all()
        persons = [row for row in results]

        logger.info(f"Found {len(persons)} emails in the person table.")
        for person in persons:
            email = person['email']
            omraade = person['omraade']
            logger.info(f"Processing email: {email}")
            found = False
            if "@" not in email or "." not in email:
                search_results = delta_client.search(email=email)
                if len(search_results) == 1:
                    new_email = search_results[0].get("E-mail") or search_results[0].get("email")
                    afdeling = search_results[0].get("Afdeling")
                    update_fields = []
                    update_values = {"old_email": email}
                    if new_email and new_email != email:
                        update_fields.append("email = :new_email")
                        update_fields.append("isystem = TRUE")
                        update_values["new_email"] = new_email
                        found = True
                        email = new_email
                    if afdeling and omraade != afdeling:
                        update_fields.append("omraade = :afdeling")
                        update_values["afdeling"] = afdeling
                    if update_fields:
                        update_query = f"""
                        UPDATE {DB_SCHEMA}.person
                        SET {', '.join(update_fields)}
                        WHERE email = :old_email
                        """
                        conn.execute(text(update_query), update_values)
                        conn.commit()
            elif not delta_client.check_email_exists(email):
                # Check if email exists in AD_DB_SCHEMA.person
                ad_query = f"""
                SELECT "Skole" FROM {AD_DB_SCHEMA}.person WHERE LOWER("Mail") = :email
                """
                ad_result = conn.execute(text(ad_query), {"email": email.lower()}).fetchone()
                if ad_result:
                    skole = ad_result[0]
                    update_query = f"""
                    UPDATE {DB_SCHEMA}.person
                    SET isystem = TRUE, omraade = :skole
                    WHERE email = :email
                    """
                    found = True
                    conn.execute(text(update_query), {"skole": skole, "email": email})
                    conn.commit()
                else:
                    ms_res = ms_graph_client.search_alias(email)
                    if len(ms_res) == 1:
                        new_email = ms_res[0].get("E-mail")
                        if new_email and new_email != email:
                            update_query = f"""
                            UPDATE {DB_SCHEMA}.person
                            SET email = :new_email, isystem = TRUE
                            WHERE email = :old_email
                            """
                            found = True
                            conn.execute(text(update_query), {"new_email": new_email, "old_email": email})
                            conn.commit()
                            email = new_email
            else:
                delta_result = delta_client.search(email=email)
                omraade_value = None
                if len(delta_result) == 1:
                    omraade_value = delta_result[0].get("Afdeling")
                if omraade_value:
                    update_query = f"""
                    UPDATE {DB_SCHEMA}.person
                    SET isystem = TRUE, omraade = :omraade
                    WHERE email = :email
                    """
                    conn.execute(text(update_query), {"email": email, "omraade": omraade_value})
                else:
                    update_query = f"""
                    UPDATE {DB_SCHEMA}.person
                    SET isystem = TRUE
                    WHERE email = :email
                    """
                    conn.execute(text(update_query), {"email": email})
                found = True
                conn.commit()

            logger.info(f"Email processed: {email}, found: {found}")


def delete_udvalg_without_parent():
    with db_client.get_connection() as conn:
        delete_query = """
        DELETE FROM meddb.udvalg
        WHERE overordnetudvalg IS NULL
            AND udvalg <> 'HOVEDUDVALG';
        """
        conn.execute(text(delete_query))
        conn.commit()


def fix_names():
    with db_client.get_connection() as conn:
        update_query = f"""
        UPDATE {DB_SCHEMA}.person
        SET navn = REPLACE(SPLIT_PART(navn, '@', 1), '.', ' ')
        WHERE navn LIKE '%@%';
        """
        conn.execute(text(update_query))
        conn.commit()


if __name__ == "__main__":  # pragma: no cover
    # sched.add_job(delete_udvalg_without_parent, 'date', run_date=datetime.now())
    # sched.add_job(fix_names, 'date', run_date=datetime.now())
    # sched.add_job(clean, 'date', run_date=datetime.now())
    # sched.add_job(daily_job, 'date', run_date=datetime.now())
    # sched.add_job(daily_job, 'cron', hour=8, minute=0, id='daily_job')
    # sched.start()
    # sys.argv = ["streamlit", "run", "Forside.py", "--client.toolbarMode=minimal", "--server.port=8080"]
    # sys.exit(stcli.main())
    pass