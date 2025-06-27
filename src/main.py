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
from utils.config import DB_HOST, DB_USER, DB_PASS, DB_NAME, DB_SCHEMA, SFTP_HOST, SFTP_USER, SFTP_PASS
from utils.logging import set_logging_configuration

# Set up logging configuration
set_logging_configuration()

logger = logging.getLogger(__name__)

sched = BackgroundScheduler()
db_client = DatabaseClient(db_type="postgresql", database=DB_NAME, username=DB_USER, password=DB_PASS, host=DB_HOST)
sftp_client = SFTPClient(host=SFTP_HOST, username=SFTP_USER, password=SFTP_PASS)

with db_client.get_connection() as conn:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
    conn.commit()


def daily_job():
    logger.info("Starting daily job to update admins from CSV file.")
    sftp_conn = sftp_client.get_connection()
    if sftp_conn is None:
        logger.error("Error: Failed to establish SFTP connection.")
        return
    with sftp_conn as sftp_conn:
        file_list = sftp_conn.listdir()
        csv_files = [file for file in file_list if file.endswith('.csv')]

        if len(csv_files) == 0:
            logger.warning("Warning: No CSV files found.")
            return
        elif len(csv_files) > 1:
            logger.warning("Warning: More than one CSV file found.")
            return
        else:
            csv_file_name = csv_files[0]

            try:
                with sftp_conn.open(csv_file_name, 'rb') as binary_file:
                    decoded_file = io.TextIOWrapper(binary_file, encoding='UTF-16')
                    df = pd.read_csv(decoded_file, sep=';')
                    df.columns = df.columns.str.lower()
                    if 'email' in df.columns:
                        df = df[['email']]
                        df['email'] = df['email'].str.lower()
                        df = df.drop_duplicates(subset=['email'], ignore_index=True)
                        with db_client.get_connection() as conn:
                            df.to_sql('administratorer', conn, schema=DB_SCHEMA, if_exists='replace', index=False)
                            conn.commit()
                            logger.info("Admins have been updated in database")
                    else:
                        logger.error("Error: 'email' column not found in the CSV file.")
                        return

            except Exception as e:
                logger.error(f"Error reading CSV file: {e}")
                return

from Forside import delta_client, ms_graph_client, AD_DB_SCHEMA

def clean_emails():
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

        # Get all emails from person table
        email_query = f"SELECT email FROM {DB_SCHEMA}.person WHERE email IS NOT NULL"
        emails = [row['email'] for row in conn.execute(text(email_query)).mappings().all()]
        # st.write("Alle e-mails i person-tabellen:")
        # st.write("; ".join(emails))
        logger.info(f"Found {len(emails)} emails in the person table.")
        for email in emails:
            logger.info(f"Processing email: {email}")
            found = False
            if "@" not in email or "." not in email:
                search_results = delta_client.search(email=email)
                if len(search_results) == 1:
                    new_email = search_results[0].get("E-mail") or search_results[0].get("email")
                    if new_email and new_email != email:
                        update_query = f"""
                        UPDATE {DB_SCHEMA}.person
                        SET isystem = TRUE
                        SET email = :new_email
                        WHERE email = :old_email
                        """
                        conn.execute(text(update_query), {"new_email": new_email, "old_email": email})
                        conn.commit()
                        found = True
                        email = new_email
            elif not delta_client.check_email_exists(email):
                # Check if email exists in AD_DB_SCHEMA.person
                ad_query = f"""
                SELECT 1 FROM {AD_DB_SCHEMA}.person WHERE LOWER("Mail") = :email
                """
                ad_result = conn.execute(text(ad_query), {"email": email.lower()}).fetchone()
                if ad_result:
                    update_query = f"""
                    UPDATE {DB_SCHEMA}.person
                    SET isystem = TRUE
                    WHERE email = :email
                    """
                    found = True
                    conn.execute(text(update_query), {"email": email})
                    conn.commit()
                else:
                    ms_res = ms_graph_client.search_alias(email)
                    if len(ms_res) == 1:
                        new_email = ms_res[0].get("E-mail")
                        if new_email and new_email != email:
                            update_query = f"""
                            UPDATE {DB_SCHEMA}.person
                            SET email = :new_email
                            SET isystem = TRUE
                            WHERE email = :old_email
                            """
                            found = True
                            conn.execute(text(update_query), {"new_email": new_email, "old_email": email})
                            conn.commit()
                            email = new_email
            else:
                update_query = f"""
                UPDATE {DB_SCHEMA}.person
                SET isystem = TRUE
                WHERE email = :email
                """
                found = True
                conn.execute(text(update_query), {"email": email})
                conn.commit()
            
            logger.info(f"Email processed: {email}, found: {found}")


if __name__ == "__main__":  # pragma: no cover
    sched.add_job(clean_emails, 'date', run_date=datetime.now())
    sched.add_job(daily_job, 'date', run_date=datetime.now())
    sched.add_job(daily_job, 'cron', hour=8, minute=0, id='daily_job')
    sched.start()
    sys.argv = ["streamlit", "run", "Forside.py", "--client.toolbarMode=minimal", "--server.port=8080"]
    sys.exit(stcli.main())
