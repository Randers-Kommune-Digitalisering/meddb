import os
from dotenv import load_dotenv


# loads .env file, will not overide already set enviroment variables (will do nothing when testing, building and deploying)
load_dotenv()

# Keycloack Auth
KEYCLOAK_URL = os.environ["KEYCLOAK_URL"].strip()
KEYCLOAK_REALM = "randers-kommune"
KEYCLOAK_CLIENT_ID = "meddb"

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
DB_PORT = os.environ.get('DB_PORT')
DB_SCHEMA = "meddb"

# Skole AD Database - same db as main but different schema
SKOLE_AD_DB_HOST = DB_HOST
SKOLE_AD_DB_USER = DB_USER
SKOLE_AD_DB_PASS = DB_PASS
SKOLE_AD_DB_NAME = DB_NAME
SKOLE_AD_DB_PORT = DB_PORT
SKOLE_AD_DB_SCHEMA = "skolead"

XFLOW_URL = "https://randers.ditmerflex.dk/randers/Login/LoginFederated?returnUrl=/randers/Opret/8d089028bce28"
PRIORITY_MEMBERS = ['Formand', 'Næstformand', 'Sekretær']
