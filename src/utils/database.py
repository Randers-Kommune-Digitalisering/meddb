import logging
import urllib.parse
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine


class DatabaseClient:
    def __init__(self, db_type: str, username: str, password: str, host: str, port: int | None = None, database: str | None = None):
        """
        Initialize the DatabaseClient with connection parameters.

        :param db_type: Type of the database (e.g., 'mssql', 'mariadb', 'postgresql').
        :type db_type: str
        :param username: Username for the database connection.
        :type username: str
        :param password: Password for the database connection.
        :type password: str
        :param host: Hostname or IP address of the database server.
        :type host: str
        :param port: Port number of the database server. (optional)
        :type port: int | None
        :param database: Name of the database to connect to. (optional)
        :type database: str | None
        """
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
        """Get the SQLAlchemy engine."""
        return self.engine

    def get_connection(self):
        """Get a connection from the SQLAlchemy engine."""
        try:
            if self.engine:
                return self.engine.connect()
            self.logger.error("DatabaseClient not initialized properly. Engine is None. Check error from init.")
        except Exception as e:
            self.logger.error(f"Error connecting to database: {e}")

    def get_session(self):
        """Get a SQLAlchemy session."""
        try:
            return self.SessionLocal()
        except Exception as e:
            self.logger.error(f"Error creating session: {e}")

    def execute_sql(self, sql, params=None):
        """Execute a raw SQL query."""
        try:
            self.SessionLocal.remove()
        except Exception as e:
            self.logger.error(f"Error removing session: {e}")
