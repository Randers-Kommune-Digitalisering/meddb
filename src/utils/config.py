import os
from dotenv import load_dotenv


# loads .env file, will not overide already set enviroment variables (will do nothing when testing, building and deploying)
load_dotenv()


DEBUG = os.getenv('DEBUG', 'False') in ['True', 'true']
PORT = os.getenv('PORT', '8080')
POD_NAME = os.getenv('POD_NAME', 'pod_name_not_set')

# Keycloack Auth
KEYCLOAK_URL = os.environ["KEYCLOAK_URL"].strip()
KEYCLOAK_REALM = "randers-kommune"
KEYCLOAK_CLIENT_ID = "meddb"

SFTP_HOST = "sftp.randers.dk"
SFTP_USER = os.environ["SFTP_USER"].strip()
SFTP_PASS = os.environ["SFTP_PASS"].strip()

# Delta API
DELTA_URL = os.environ['DELTA_URL'].rstrip()
DELTA_CLIENT_ID = os.environ["DELTA_CLIENT_ID"].strip()
DELTA_CLIENT_SECRET = os.environ["DELTA_CLIENT_SECRET"].strip()
DELTA_REALM = '730'
DELTA_AUTH_URL = "https://idp.opus-universe.kmd.dk"

# Database
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_NAME = os.environ.get('DB_NAME')
DB_SCHEMA = "meddb"

AD_DB_SCHEMA = "skolead"

# Skole AD Database
SKOLE_AD_DB_HOST = None
SKOLE_AD_DB_USER = None
SKOLE_AD_DB_PASS = None
SKOLE_AD_DB_NAME = None
SKOLE_AD_DB_SCHEMA = None
