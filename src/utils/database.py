import logging
import urllib.parse
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine


class DatabaseClient:
    def __init__(self, db_type: str, username: str, password: str, host: str, port: int | None = None, database: str | None = None):
        self.db_type = db_type.lower()
        self.database = database
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.logger = logging.getLogger(__name__)

        if self.db_type == 'mssql':
            driver = 'mssql+pymssql'
        elif self.db_type == 'mariadb':
            driver = 'mariadb+mariadbconnector'
        elif self.db_type == 'postgresql':
            driver = 'postgresql+psycopg2'
        else:
            raise ValueError(f"Invalid database type {self.db_type}")

        connection_string = f'{driver}://{urllib.parse.quote_plus(username)}:{urllib.parse.quote_plus(password)}@{urllib.parse.quote_plus(host)}'

        if port is not None:
            connection_string += f':{urllib.parse.quote_plus(str(port))}'

        if database:
            connection_string += f'/{urllib.parse.quote_plus(database)}'

        self.engine = create_engine(connection_string, pool_pre_ping=True)
        self.SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))

    def get_engine(self):
        return self.engine

    def get_session(self):
        """
        Returns a new SQLAlchemy session. For Streamlit, use as context manager:
        with db_client.get_session() as session:
            ...
        """
        try:
            return self.SessionLocal()
        except Exception as e:
            self.logger.error(f"Error creating session: {e}")

    def remove_session(self):
        """
        Removes the current session (call at end of request if needed).
        """
        try:
            self.SessionLocal.remove()
        except Exception as e:
            self.logger.error(f"Error removing session: {e}")
