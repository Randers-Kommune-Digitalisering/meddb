import logging

from sqlalchemy import text

from utils.config import SKOLE_AD_DB_HOST, SKOLE_AD_DB_USER, SKOLE_AD_DB_PASS, SKOLE_AD_DB_NAME, SKOLE_AD_DB_SCHEMA, SKOLE_AD_DB_PORT
from utils.database import DatabaseClient


logger = logging.getLogger(__name__)


class SchoolData:
    """
    Class to interact with the Skole AD database to search for person records.
    Schema and models assumed to be controlled externally.
    """
    def __init__(self):
        """Initialize the SchoolData with a DatabaseClient connected to the Skole AD database."""
        self.db_client = DatabaseClient(
            db_type="postgresql",
            database=SKOLE_AD_DB_NAME,
            username=SKOLE_AD_DB_USER,
            password=SKOLE_AD_DB_PASS,
            host=SKOLE_AD_DB_HOST,
            port=SKOLE_AD_DB_PORT
        )

    def search_person(self, username: str | None = None, name: str | None = None, email: str | None = None) -> dict:
        """
        Search for a person in the Skole AD database by username, name, or email. Must provide at least one parameter.
        Returns a list of dictionaries with keys: 'Brugernavn', 'Navn', 'E-mail', 'Afdeling'.
        """
        with self.db_client.get_connection() as conn:
            search_clauses = []
            params = {}
            if username:
                search_clauses.append('LOWER("DQnummer") = :username')
                params["username"] = username.lower()
            if name:
                search_clauses.append('LOWER("Navn") LIKE :name')
                params["name"] = f"%{name.lower()}%"
            if email:
                search_clauses.append('LOWER("Mail") = :email')
                params["email"] = email.lower()
            if search_clauses:
                ad_query = f"""
                    SELECT "DQnummer" as Brugernavn, "Navn", "Mail" as email, "Skole"
                    FROM {SKOLE_AD_DB_SCHEMA}.person
                    WHERE {' OR '.join(search_clauses)}
                    LIMIT 10
                """
                ad_result = conn.execute(text(ad_query), params).mappings().all()

                ad_res = [
                    {
                        "Brugernavn": row.get("Brugernavn", ""),
                        "Navn": row["Navn"],
                        "E-mail": row["email"],
                        "Afdeling": row.get("Skole", "")
                    }
                    for row in ad_result
                ]
                return ad_res
            else:
                raise ValueError("At least one search parameter must be provided.")
