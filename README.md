# MED-database
Webapp for MED-database. All users as well as public acccess can see the data. Certain roles can add/remove members from committees or create/delete/edit committees.

## Dependencies
Is depended on Skole AD being updated from this [api](https://github.com/Randers-Kommune-Digitalisering/external-api)
dag_meddb_person_check DAG in [Airflow](https://github.com/Randers-Kommune-Digitalisering/airflow) checks if all people in the database can be found in external systems.

### Keycloak
Client ID: meddb
Roles: edit_member (add/delete members), edit_udvalg (create/delete/edit committees)

### Database
Uses postgres database "meta" with the schemas "meddb" and "skolead"

### APIs
Uses Delta and MSGraph apis.
"Delta prod (ny)" and "Azure AD token" in BitWarden

## Run locally
* Install python and requirements in [requirements.txt](src/requirements.txt)
* Setup a postgres datbase with schema "skolead" and table "person"
* run the app with `streamlit run src\main.py`