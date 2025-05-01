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
from utils.config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from utils.logging import set_logging_configuration

# Set up logging configuration
set_logging_configuration()

logger = logging.getLogger(__name__)

SCHEMA = "meddb"
sched = BackgroundScheduler()
db_client = DatabaseClient(db_type="postgresql", database=DB_NAME, username=DB_USER, password=DB_PASS, host=DB_HOST)
sftp_client = SFTPClient(host="sftp.randers.dk", username="SFTP-SDRoller", password="***REMOVED***")

with db_client.get_connection() as conn:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    conn.commit()


def daily_job():
    with sftp_client.get_connection() as sftp_conn:
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
                            df.to_sql('administratorer', conn, schema=SCHEMA, if_exists='replace', index=False)
                            conn.commit()
                            logger.info("Admins have been updated in database")
                    else:
                        logger.error("Error: 'email' column not found in the CSV file.")
                        return

            except Exception as e:
                logger.error(f"Error reading CSV file: {e}")
                return


if __name__ == "__main__":  # pragma: no cover
    sched.add_job(daily_job, 'date', run_date=datetime.now())
    sched.add_job(daily_job, 'cron', hour=8, minute=0, id='daily_job')
    sched.start()
    sys.argv = ["streamlit", "run", "streamlit_app.py", "--client.toolbarMode=minimal", "--server.port=8080"]
    sys.exit(stcli.main())
