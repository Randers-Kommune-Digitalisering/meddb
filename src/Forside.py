import pandas as pd
import streamlit as st
from streamlit_keycloak import login
from streamlit_tree_select import tree_select

from sqlalchemy import text
from main import DB_SCHEMA, db_client
from delta import DeltaClient
from ms_graph import MSGraphClient
from utils.config import KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID, AD_DB_SCHEMA


delta_client = DeltaClient()
ms_graph_client = MSGraphClient()


st.set_page_config(page_title="MED-Database", page_icon="🗄️", layout="wide")
st.markdown('<style>table {width:100%;}</style>', unsafe_allow_html=True)

# Fetch rows from the database only once
if "udvalg_data" not in st.session_state:
    with db_client.get_connection() as conn:
        try:
            query = 'SELECT id, overordnetudvalg, udvalg FROM meddb.udvalg'
            result = conn.execute(text(query))
            st.session_state.udvalg_data = result.mappings().all()
        except Exception as e:
            st.error(f"Error fetching data from the database: {e}")
            st.session_state.udvalg_data = None

if "checked_nodes" not in st.session_state:
    st.session_state.checked_nodes = []

if "expanded_nodes" not in st.session_state:
    st.session_state.expanded_nodes = []

if "show_success" not in st.session_state:
    st.session_state.show_success = False

keycloak = login(
    url=KEYCLOAK_URL,
    realm=KEYCLOAK_REALM,
    client_id=KEYCLOAK_CLIENT_ID
)

if keycloak.authenticated:
    email = keycloak.user_info['email'].lower()
    try:
        with db_client.get_connection() as conn:
            query = f"SELECT 1 FROM {DB_SCHEMA}.administratorer WHERE LOWER(email) = :email"
            result = conn.execute(text(query), {"email": email}).fetchone()
            is_admin = result is not None
        if is_admin:
            st.write(f"{keycloak.user_info['name']} er logget ind som administrator")
        else:
            st.write(f"{keycloak.user_info['name']} er logget ind som bruger")
    except Exception as e:
        is_admin = False
        print(f"Fejl ved tjek af administratorstatus: {e}")
else:
    is_admin = False
    email = None

if email == 'rune.aagaard.keena@randers.dk':
    is_admin = True

    # if st.button("Gør 'person.id' til auto-increment (SERIAL)", key="make_person_id_serial"):
    #     with db_client.get_connection() as conn:
    #         try:
    #             # Check if 'id' is already serial/identity
    #             check_query = f"""
    #             SELECT column_default
    #             FROM information_DB_SCHEMA.columns
    #             WHERE table_name = 'person' AND column_name = 'id' AND table_DB_SCHEMA = '{DB_SCHEMA}'
    #             """
    #             result = conn.execute(text(check_query)).fetchone()
    #             if result and result[0] and ("nextval" in str(result[0]) or "identity" in str(result[0]).lower()):
    #                 st.info("'person.id' er allerede auto-increment.")
    #             else:
    #                 # Find current max id
    #                 st.info('Setting up auto-increment for person.id')
    #                 max_id_result = conn.execute(
    #                     text(f"SELECT COALESCE(MAX(id), 0) FROM {DB_SCHEMA}.person")
    #                 ).fetchone()
    #                 max_id = max_id_result[0] if max_id_result else 0

    #                 # Create or update sequence to start after max id
    #                 seq_name = f"{DB_SCHEMA}.person_id_seq"
    #                 conn.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START WITH {max_id + 1} OWNED BY {DB_SCHEMA}.person.id"))
    #                 conn.execute(text(f"SELECT setval('{seq_name}', GREATEST((SELECT COALESCE(MAX(id), 0) FROM {DB_SCHEMA}.person), 0) + 1, false)"))
    #                 conn.execute(text(f"ALTER TABLE {DB_SCHEMA}.person ALTER COLUMN id SET DEFAULT nextval('{seq_name}')"))
    #                 conn.commit()
    #                 st.success("'person.id' er nu auto-increment og vil altid være én større end det højeste eksisterende id.")
    #         except Exception as e:
    #             st.error(f"Kunne ikke ændre 'person.id' til auto-increment: {e}")

    uploaded_file = st.file_uploader("Upload file", type=["csv"], label_visibility="collapsed")
    if uploaded_file is not None:
        file_base_name = uploaded_file.name.split(".")
        if len(file_base_name) == 2:
            table_name = file_base_name[0]
            table_name = table_name.lower()
            with db_client.get_connection() as conn:

                dataframe = pd.read_csv(uploaded_file, delimiter=";", encoding="utf-8", low_memory=False)

                dataframe = dataframe.dropna(axis=1, how='all')

                dataframe.columns = [col.lower() for col in dataframe.columns]

                if 'adgangskode' in dataframe.columns and 'brugernavn' not in dataframe.columns:
                    dataframe['brugernavn'] = ""

                for col_to_drop in ['adgangskode', 'omraade', 'titel', 'fagnavn', 'privatemail']:
                    if col_to_drop in dataframe.columns:
                        dataframe = dataframe.drop(columns=[col_to_drop])

                if 'titelkursus' in dataframe.columns:
                    dataframe = dataframe[dataframe['titelkursus'].notna()]

                if 'udvalg' in dataframe.columns:
                    dataframe = dataframe[dataframe['udvalg'].notna()]

                columns = []
                for col_name, dtype in zip(dataframe.columns, dataframe.dtypes):
                    if col_name == "id":
                        columns.append(f"{col_name} INTEGER PRIMARY KEY")
                    elif col_name.endswith("Id"):
                        columns.append(f"{col_name} INTEGER")
                    elif pd.api.types.is_integer_dtype(dtype):
                        columns.append(f"{col_name} INTEGER")
                    elif pd.api.types.is_float_dtype(dtype):
                        columns.append(f"{col_name} FLOAT")
                    elif pd.api.types.is_bool_dtype(dtype):
                        columns.append(f"{col_name} BOOLEAN")
                    elif pd.api.types.is_datetime64_any_dtype(dtype):
                        columns.append(f"{col_name} TIMESTAMP")
                    else:
                        columns.append(f"{col_name} TEXT")

                create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.{table_name} (
                    {', '.join(columns)}
                )
                """

                conn.execute(text(create_table_query))
                conn.commit()

                for col_name in dataframe.columns:
                    if col_name.endswith("Id") and col_name != "id":
                        referenced_table = col_name[:-2].lower()
                        if referenced_table == "fag":
                            referenced_table = "fagforening"
                        add_foreign_key_query = f"""
                        ALTER TABLE {DB_SCHEMA}.{table_name}
                        ADD CONSTRAINT fk_{table_name}_{col_name}
                        FOREIGN KEY ({col_name})
                        REFERENCES {DB_SCHEMA}.{referenced_table}(Id)
                        ON DELETE CASCADE
                        """
                        conn.execute(text(add_foreign_key_query))
                        conn.commit()

                dataframe.to_sql(table_name, conn, if_exists="append", index=False, schema=DB_SCHEMA)

                st.success(f"The table '{table_name}' has been created successfully.")
                # If 'id' column exists, make it auto-increment (SERIAL/IDENTITY)
                if "id" in dataframe.columns:
                    try:
                        # Check if 'id' is already serial/identity
                        check_query = f"""
                        SELECT column_default
                        FROM information_schema.columns
                        WHERE table_name = '{table_name}' AND column_name = 'id' AND table_schema = '{DB_SCHEMA}'
                        """
                        result = conn.execute(text(check_query)).fetchone()
                        if not (result and result[0] and ("nextval" in str(result[0]) or "identity" in str(result[0]).lower())):
                            # Find current max id
                            max_id_result = conn.execute(
                                text(f"SELECT COALESCE(MAX(id), 0) FROM {DB_SCHEMA}.{table_name}")
                            ).fetchone()
                            max_id = max_id_result[0] if max_id_result else 0

                            seq_name = f"{DB_SCHEMA}.{table_name}_id_seq"
                            conn.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START WITH {max_id + 1} OWNED BY {DB_SCHEMA}.{table_name}.id"))
                            conn.execute(text(f"SELECT setval('{seq_name}', GREATEST((SELECT COALESCE(MAX(id), 0) FROM {DB_SCHEMA}.{table_name}), 0) + 1, false)"))
                            conn.execute(text(f"ALTER TABLE {DB_SCHEMA}.{table_name} ALTER COLUMN id SET DEFAULT nextval('{seq_name}')"))
                            st.info(f"'id' column in '{table_name}' is now auto-increment.")
                        else:
                            st.info(f"'id' column in '{table_name}' is already auto-increment.")
                    except Exception as e:
                        st.error(f"Could not set 'id' column to auto-increment: {e}")
                else:
                    # Add a unique constraint on all columns containing 'id'
                    id_columns = [col for col in dataframe.columns if 'id' in col.lower()]
                    if id_columns:
                        constraint_name = f"{table_name}_{'_'.join(id_columns)}_unique"
                        unique_constraint_query = f"""
                        ALTER TABLE {DB_SCHEMA}.{table_name}
                        ADD CONSTRAINT {constraint_name}
                        UNIQUE ({', '.join(id_columns)})
                        """
                        try:
                            conn.execute(text(unique_constraint_query))
                            st.info(f"Unique constraint added on columns: {', '.join(id_columns)}")
                        except Exception as e:
                            st.warning(f"Could not add unique constraint: {e}")
                conn.commit()
        else:
            st.error("File name is not valid. Please use a file name with only one dot.")
            result = conn.execute(text("SELECT table_name FROM information_DB_SCHEMA.tables WHERE table_DB_SCHEMA = 'public'"))
            tables = [row['table_name'] for row in result]
            st.write("Tables in the database:", tables)

    if st.button("Clean"):
        with db_client.get_connection() as conn:
            try:
                # Delete orphaned personrolle rows
                delete_orphan_personrolle = f"""
                DELETE FROM {DB_SCHEMA}.personrolle
                WHERE personid NOT IN (SELECT id FROM {DB_SCHEMA}.person)
                   OR rolleid NOT IN (SELECT id FROM {DB_SCHEMA}.rolle)
                   OR udvalgsid NOT IN (SELECT id FROM {DB_SCHEMA}.udvalg)
                """
                conn.execute(text(delete_orphan_personrolle))
                conn.commit()

                # Delete persons without any roles
                delete_query = f"""
                DELETE FROM {DB_SCHEMA}.person
                WHERE id NOT IN (
                    SELECT DISTINCT personid FROM {DB_SCHEMA}.personrolle
                )
                """
                conn.execute(text(delete_query))
                conn.commit()
                st.success("Alle personer uden tilknyttet rolle og alle ugyldige personrolle-rækker er slettet.")
            except Exception as e:
                st.error(f"Kunne ikke slette personer eller personrolle uden gyldige referencer: {e}")

    if st.button("Check mails"):
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
                st.info("'isystem' column added to person table.")

            # Get all emails from person table
            email_query = f"SELECT email FROM {DB_SCHEMA}.person WHERE email IS NOT NULL"
            emails = [row['email'] for row in conn.execute(text(email_query)).mappings().all()]
            # st.write("Alle e-mails i person-tabellen:")
            # st.write("; ".join(emails))
            for email in emails:
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
                            email = new_email
                if not delta_client.check_email_exists(email):
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
                                conn.execute(text(update_query), {"new_email": new_email, "old_email": email})
                                conn.commit()
                                email = new_email
                else:
                    update_query = f"""
                    UPDATE {DB_SCHEMA}.person
                    SET isystem = TRUE
                    WHERE email = :email
                    """
                    conn.execute(text(update_query), {"email": email})
                    conn.commit()

rows = st.session_state.udvalg_data

if rows:
    nodes = []
    row_dict = {row['id']: {'label': row['udvalg'], 'value': row['id']} for row in rows}

    for row in rows:
        parent_id = row['overordnetudvalg']
        if parent_id is None:  # and row['udvalg'] == 'HOVEDUDVALG':
            nodes.append(row_dict[row['id']])
        else:
            if parent_id in row_dict:
                if 'children' not in row_dict[parent_id]:
                    row_dict[parent_id]['children'] = []
                row_dict[parent_id]['children'].append(row_dict[row['id']])

    def sort_nested_list_of_dicts(data):
        if data is None:
            return None
        elif isinstance(data, list):
            cleaned = [sort_nested_list_of_dicts(item) for item in data if item is not None]
            return sorted(
                cleaned,
                key=lambda x: (
                    0 if isinstance(x.get('children'), list) and x['children'] else 1,
                    str(x.get('label') or '')
                )
            )
        elif isinstance(data, dict):
            sorted_dict = {k: sort_nested_list_of_dicts(v) for k, v in data.items()}
            if 'children' in sorted_dict and isinstance(sorted_dict['children'], list):
                sorted_dict['children'] = sort_nested_list_of_dicts(sorted_dict['children'])
            return sorted_dict
        else:
            return data
    nodes = sort_nested_list_of_dicts(nodes)

    if is_admin:
        edit_mode = st.session_state.get("editing", False)
        if is_admin and st.session_state.get("editing", False):
            st.markdown("<span style='font-size:2em; color:red; font-weight:bold;'>Du er ved at redigere</span>", unsafe_allow_html=True)
        if st.button("Rediger" if not edit_mode else "Afslut redigering", key="toggle_editing"):
            st.session_state.editing = not edit_mode
            st.rerun()

    with st.sidebar:
        st.subheader("Udvalg")
        selected = tree_select(
            nodes,
            no_cascade=True,
            expanded=st.session_state.expanded_nodes,
            checked=st.session_state.checked_nodes
        )

        if selected:
            new_checked_nodes = selected.get("checked", [])
            if len(new_checked_nodes) == 0:
                st.session_state.checked_nodes = []
                st.session_state.expanded_nodes = []

            if len(new_checked_nodes) == 2:
                new_checked_nodes = [node for node in new_checked_nodes if node not in st.session_state.checked_nodes]

            if len(new_checked_nodes) == 1:
                expanded_nodes = []
                current_node = int(new_checked_nodes[0])
                while current_node is not None:
                    expanded_nodes.append(current_node)
                    parent_node = next((row['overordnetudvalg'] for row in rows if row['id'] == current_node), None)
                    current_node = parent_node

                st.session_state.expanded_nodes = expanded_nodes

            if len(new_checked_nodes) == 1 and new_checked_nodes != st.session_state.checked_nodes:
                st.session_state.checked_nodes = new_checked_nodes
                st.rerun()

            if len(new_checked_nodes) == 2:
                st.session_state.checked_nodes = [new_checked_nodes[-1]]
                st.rerun()

            if len(new_checked_nodes) > 2:
                st.warning("Multiple nodes selected. Resetting selection...")
                st.session_state.checked_nodes = []
                st.rerun()

    if st.session_state.get("show_success", False):
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.success(st.session_state.get("success_message", " "))
            if st.button("OK"):
                st.session_state.show_success = False
                st.session_state.success_message = ""
                st.rerun()
        st.stop()
    elif st.session_state.checked_nodes:
        item = st.session_state.checked_nodes[0]
        selected_node = row_dict.get(int(item), {})
        if selected_node:
            st.header(selected_node.get('label', 'Unknown'))

            if is_admin and st.session_state.get("editing", False):
                col_add, col_move = st.columns([1, 1])

                if is_admin and st.session_state.get("editing", False):
                    with col_add:
                        res = st.session_state.get("people_search", [])
                        st.subheader("Tilføj medlem")
                        with st.form("search_form", clear_on_submit=True):
                            # Input fields for search
                            username = st.text_input("Brugernavn")
                            name = st.text_input("Navn")
                            email = st.text_input("E-mail")

                            search = st.form_submit_button("Søg")
                            if search:
                                if not username and not name and not email:
                                    st.error("Indtast mindst ét søgekriterie: brugernavn, navn eller e-mail.")
                                    st.stop()
                                res = delta_client.search(search_name=name, email=email, username=username)
                                # Search AD_DB_SCHEMA.person for matching users
                                with db_client.get_connection() as conn:
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
                                            FROM {AD_DB_SCHEMA}.person
                                            WHERE {' OR '.join(search_clauses)}
                                            LIMIT 10
                                        """
                                        ad_result = conn.execute(text(ad_query), params).mappings().all()
                                        # Convert AD result to match expected keys
                                        ad_res = [
                                            {
                                                "Brugernavn": row.get("Brugernavn", ""),
                                                "Navn": row["Navn"],
                                                "E-mail": row["email"],
                                                "Afdeling": row.get("Skole", "")
                                            }
                                            for row in ad_result
                                        ]
                                        # Add to existing results
                                        res.extend(ad_res)
                                st.session_state.people_search = res

                            clear_search = st.form_submit_button("Nulstil søgning", disabled=not res)
                            if clear_search:
                                st.session_state.people_search = []
                                st.rerun()

                        if res:
                            with db_client.get_connection() as conn:
                                rolle_options = {}
                                fagforening_options = {}

                                rolle_query = f"SELECT titelkursus, id FROM {DB_SCHEMA}.rolle"
                                rolle_result = conn.execute(text(rolle_query)).fetchall()
                                rolle_options = {row[0]: row[1] for row in rolle_result}

                                fag_query = f"SELECT navn, id FROM {DB_SCHEMA}.fagforening"
                                fag_result = conn.execute(text(fag_query)).fetchall()
                                fagforening_options = {"Ingen": None}
                                fagforening_options.update({row[0]: row[1] for row in fag_result})

                                expand = True if len(res) == 1 else False
                                for r in res:
                                    with st.expander(r['Navn'], expanded=expand):
                                        with st.form(f"add_member_form_{r['Navn']}_{r['Afdeling']}", clear_on_submit=True):
                                            top_line = '| ' + ' | '.join(['Navn', 'Afdeling']) + ' |' + '\n| ' + ' | '.join(['---'] * 2) + ' |' + '\n| ' + ' | '.join([r['Navn'], r['Afdeling']]) + ' |'
                                            buttom_line = '| ' + ' | '.join(['Brugernavn', 'E-mail']) + ' |' + '\n| ' + ' | '.join(['---'] * 2) + ' |' + '\n| ' + ' | '.join([r['Brugernavn'], r['E-mail']]) + ' |'
                                            st.markdown(top_line)
                                            st.markdown(buttom_line)
                                            rolle = st.selectbox(
                                                "Rolle",
                                                list(rolle_options.keys()),
                                                index=list(rolle_options.keys()).index("Medlem") if "Medlem" in rolle_options else 0,
                                                key=f"rolle_{r['Navn']}_{r['Afdeling']}"
                                            )
                                            union = st.selectbox(
                                                "Fagforening",
                                                list(fagforening_options.keys()),
                                                index=list(fagforening_options.keys()).index("Ingen"),
                                                key=f"union_{r['Navn']}_{r['Afdeling']}"
                                            )
                                            add_btn = st.form_submit_button("Tilføj")
                                            if add_btn:
                                                with db_client.get_connection() as conn:
                                                    person_result = conn.execute(
                                                        text(f"SELECT id, fagid FROM {DB_SCHEMA}.person WHERE email = :email"),
                                                        {"email": r['E-mail']}
                                                    ).mappings().fetchone()
                                                    if person_result:
                                                        person_id = person_result['id']
                                                        # Update fagforening if selected and different
                                                        selected_fagforening_id = fagforening_options[union]
                                                        if selected_fagforening_id is not None and person_result['fagid'] != selected_fagforening_id:
                                                            update_query = text(f"""
                                                                UPDATE {DB_SCHEMA}.person
                                                                SET fagid = :fagid, isystem = TRUE
                                                                WHERE id = :person_id
                                                            """)
                                                            conn.execute(update_query, {
                                                                "fagid": selected_fagforening_id,
                                                                "person_id": person_id
                                                            })
                                                            conn.commit()
                                                    else:
                                                        if fagforening_options[union] is not None:
                                                            insert_person = text(f"""
                                                                INSERT INTO {DB_SCHEMA}.person (navn, email, brugernavn, fagid, isystem)
                                                                VALUES (:navn, :email, :brugernavn, :fagid, TRUE)
                                                                RETURNING id
                                                            """)
                                                            person_id = conn.execute(
                                                                insert_person,
                                                                {
                                                                    "navn": r['Navn'],
                                                                    "email": r['E-mail'],
                                                                    "brugernavn": r['Brugernavn'],
                                                                    "fagid": fagforening_options[union]
                                                                }
                                                            ).scalar()
                                                        else:
                                                            insert_person = text(f"""
                                                                INSERT INTO {DB_SCHEMA}.person (navn, email, brugernavn, isystem)
                                                                VALUES (:navn, :email, :brugernavn, TRUE)
                                                                RETURNING id
                                                            """)
                                                            person_id = conn.execute(
                                                                insert_person,
                                                                {
                                                                    "navn": r['Navn'],
                                                                    "email": r['E-mail'],
                                                                    "brugernavn": r['Brugernavn']
                                                                }
                                                            ).scalar()
                                                        st.info(f"Ny person {r['Navn']} er oprettet med ID {person_id}.")
                                                        conn.commit()
                                                    insert_role = text(f"""
                                                        INSERT INTO {DB_SCHEMA}.personrolle (personid, rolleid, udvalgsid)
                                                        VALUES (:personid, :rolleid, :udvalgsid)
                                                        ON CONFLICT DO NOTHING
                                                    """)
                                                    conn.execute(insert_role, {
                                                        "personid": person_id,
                                                        "rolleid": rolle_options[rolle],
                                                        "udvalgsid": selected_node['value']
                                                    })
                                                    conn.commit()
                                                st.session_state.success_message = (f"{r['Navn']} er tilføjet som {rolle} til {selected_node['label']}.")
                                                st.session_state.show_success = True
                                                st.rerun()

                    with col_move:
                        st.subheader("Flyt udvalg")
                        with st.form("move_udvalg_form", clear_on_submit=True):
                            # Find current parent
                            current_udvalg_id = selected_node['value']
                            current_parent_id = next((row['overordnetudvalg'] for row in rows if row['id'] == current_udvalg_id), None)
                            current_parent_label = next((row['udvalg'] for row in rows if row['id'] == current_parent_id), "Ingen (øverste niveau)")
                            st.write(f"Nuværende overordnet udvalg: **{current_parent_label}**")

                            # Only show selectbox if not top level
                            # if current_parent_id is not None:
                            if current_udvalg_id != 1:
                                all_udvalg = [
                                    {"label": row["udvalg"], "value": row["id"]}
                                    for row in rows if row["id"] != current_udvalg_id
                                ]

                                # Find index of current parent in all_udvalg
                                default_index = 0
                                if all_udvalg and current_parent_id is not None:
                                    for idx, udv in enumerate(all_udvalg):
                                        if udv["value"] == current_parent_id:
                                            default_index = idx
                                            break

                                new_parent = st.selectbox(
                                    "Vælg nyt overordnet udvalg",
                                    options=all_udvalg,
                                    format_func=lambda x: x["label"] if isinstance(x, dict) else str(x),
                                    index=default_index if all_udvalg else None,
                                    key="move_parent_select"
                                ) if all_udvalg else None
                            else:
                                new_parent = None
                                st.info("Dette udvalg er på øverste niveau og kan ikke flyttes.")

                            submitted = st.form_submit_button("Flyt udvalg", disabled=new_parent is None)
                            if submitted:
                                if current_parent_id is None or not new_parent:
                                    st.warning("Vælg et nyt overordnet udvalg.")
                                else:
                                    with db_client.get_connection() as conn:
                                        update_query = f"""
                                        UPDATE {DB_SCHEMA}.udvalg
                                        SET overordnetudvalg = :new_parent_id
                                        WHERE id = :udvalg_id
                                        """
                                        conn.execute(
                                            text(update_query),
                                            {"new_parent_id": new_parent["value"], "udvalg_id": current_udvalg_id}
                                        )
                                        conn.commit()
                                    st.session_state.pop("udvalg_data", None)
                                    st.session_state.show_success = True
                                    st.session_state.success_message = f"{selected_node.get('label', 'Udvalg')} er flyttet under {new_parent['label']}."
                                    st.rerun()

                        st.subheader("Omdøb udvalg")
                        with st.form("rename_udvalg_form", clear_on_submit=True):
                            current_udvalg_id = selected_node['value']
                            current_label = selected_node.get('label', '')
                            new_label = st.text_input("Nyt navn for udvalg", value=current_label)
                            rename_submitted = st.form_submit_button("Omdøb")
                            if rename_submitted:
                                if not new_label.strip():
                                    st.warning("Navnet må ikke være tomt.")
                                elif new_label.strip() == current_label:
                                    st.info("Navnet er uændret.")
                                else:
                                    with db_client.get_connection() as conn:
                                        update_query = f"""
                                        UPDATE {DB_SCHEMA}.udvalg
                                        SET udvalg = :new_label
                                        WHERE id = :udvalg_id
                                        """
                                        conn.execute(
                                            text(update_query),
                                            {"new_label": new_label.strip(), "udvalg_id": current_udvalg_id}
                                        )
                                        conn.commit()
                                    st.session_state.pop("udvalg_data", None)
                                    st.session_state.show_success = True
                                    st.session_state.success_message = f"Udvalg er omdøbt til '{new_label.strip()}'."
                                    st.rerun()

                        st.subheader("Slet udvalg")
                        with st.container(border=True):
                            st.warning(
                                "Advarsel: Sletning af et udvalg vil også slette alle tilknyttede personroller. "
                                "Denne handling kan ikke fortrydes."
                            )
                            confirm_delete = st.checkbox(f'Jeg bekræfter, at jeg vil slette udvalget "{selected_node.get("label", "")}" permanent.')
                            if confirm_delete and not st.session_state.get("confirm_delete_checked", False):
                                st.session_state["confirm_delete_checked"] = True
                                st.rerun()
                            elif not confirm_delete and st.session_state.get("confirm_delete_checked", False):
                                st.session_state["confirm_delete_checked"] = False
                                st.rerun()
                            delete_submitted = st.button("Slet udvalg", disabled=not confirm_delete)
                            if delete_submitted:
                                with db_client.get_connection() as conn:
                                    # Slet alle personroller tilknyttet dette udvalg
                                    conn.execute(
                                        text(f"DELETE FROM {DB_SCHEMA}.personrolle WHERE udvalgsid = :udvalg_id"),
                                        {"udvalg_id": selected_node['value']}
                                    )
                                    # Sæt overordnetudvalg til NULL for eventuelle underudvalg
                                    conn.execute(
                                        text(f"UPDATE {DB_SCHEMA}.udvalg SET overordnetudvalg = NULL WHERE overordnetudvalg = :udvalg_id"),
                                        {"udvalg_id": selected_node['value']}
                                    )
                                    # Slet selve udvalget
                                    conn.execute(
                                        text(f"DELETE FROM {DB_SCHEMA}.udvalg WHERE id = :udvalg_id"),
                                        {"udvalg_id": selected_node['value']}
                                    )
                                    # Slet personer uden nogen personrolle
                                    conn.execute(
                                        text(f"""
                                            DELETE FROM {DB_SCHEMA}.person
                                            WHERE id NOT IN (
                                                SELECT DISTINCT personid FROM {DB_SCHEMA}.personrolle
                                            )
                                        """)
                                    )
                                    conn.commit()
                                st.session_state.pop("udvalg_data", None)
                                st.session_state.show_success = True
                                st.session_state.success_message = f"Udvalg '{selected_node.get('label', '')}' er slettet."
                                st.session_state.checked_nodes = []
                                st.rerun()

            with db_client.get_connection() as conn:
                query = f"""
                SELECT p.navn, r.titelkursus as rolle, p.email, p.isystem
                FROM {DB_SCHEMA}.personrolle pr
                JOIN {DB_SCHEMA}.rolle r ON pr.rolleid = r.id
                JOIN {DB_SCHEMA}.person p ON pr.personid = p.id
                WHERE pr.udvalgsid = :udvalgsid
                """
                result = conn.execute(text(query), {"udvalgsid": selected_node['value']})
                roles_and_persons = result.mappings().all()

            if roles_and_persons:
                emails = [row["email"] for row in roles_and_persons if row["email"]]
                if emails:
                    mailto_link = f"mailto:{';'.join(emails)}"
                    st.markdown(
                        f'<a href="{mailto_link}" target="_blank"><button type="button">Send e-mail til alle i udvalg</button></a>',
                        unsafe_allow_html=True
                    )

                priority_roles = ['Formand', 'Næstformand', 'Sekretær', 'Udvalgsadministrator']

                def get_priority(role):
                    return priority_roles.index(role) if role in priority_roles else len(priority_roles)

                sorted_rows = sorted(
                    roles_and_persons,
                    key=lambda x: (get_priority(x['rolle']), x['rolle'], x['navn'])
                )

                cols = st.columns([2, 2, 2, 1]) if is_admin and st.session_state.get("editing", False) else st.columns([2, 2, 2])
                cols[0].markdown("<span style='font-size:1.2em; font-weight:bold;'>Navn</span>", unsafe_allow_html=True)
                cols[1].markdown("<span style='font-size:1.2em; font-weight:bold;'>Rolle</span>", unsafe_allow_html=True)
                cols[2].markdown("<span style='font-size:1.2em; font-weight:bold;'>Email</span>", unsafe_allow_html=True)
                if is_admin and st.session_state.get("editing", False):
                    cols[3].write(' ')

                for i, row in enumerate(sorted_rows):
                    cols = st.columns([2, 2, 2, 1]) if is_admin and st.session_state.get("editing", False) else st.columns([2, 2, 2])
                    cols[0].markdown(f"<span>{row['navn']}</span>", unsafe_allow_html=True)
                    cols[1].markdown(f"<span>{row['rolle']}</span>", unsafe_allow_html=True)
                    if not row.get("isystem"):
                        email_link = f'<span>{row["email"]} ❌</span>'
                    else:
                        email_link = f'<span>{row["email"]}</span>'
                    cols[2].markdown(email_link, unsafe_allow_html=True)
                    if is_admin and st.session_state.get("editing", False):
                        if cols[3].button("Fjern", key=f"slet_{row['navn']}_{row['rolle']}_{row['email']}"):
                            with db_client.get_connection() as conn:
                                # Delete the personrolle entry
                                delete_query = f"""
                                DELETE FROM {DB_SCHEMA}.personrolle
                                WHERE udvalgsid = :udvalgsid
                                AND personid = (SELECT id FROM {DB_SCHEMA}.person WHERE email = :email)
                                """
                                conn.execute(
                                    text(delete_query),
                                    {"udvalgsid": selected_node['value'], "email": row['email']}
                                )
                                # Delete the person if they have no other personrolle
                                cleanup_query = f"""
                                DELETE FROM {DB_SCHEMA}.person
                                WHERE email = :email
                                  AND id NOT IN (
                                    SELECT personid FROM {DB_SCHEMA}.personrolle
                                  )
                                """
                                conn.execute(
                                    text(cleanup_query),
                                    {"email": row['email']}
                                )
                                conn.commit()
                            st.session_state.show_success = True
                            st.session_state.success_message = f"{row['rolle']} {row['navn']} er fjernet fra {selected_node['label']}."
                            st.rerun()
            else:
                st.write("Ingen personer fundet på det valgte udvalg.")
        else:
            st.error("Selected node not found.")
    else:
        st.write("Intet udvalg valgt.")
        st.subheader("Søg udvalg")
        search_query = st.text_input("Søg efter udvalg...", key="udvalg_search")
        if search_query:
            filtered = [row for row in rows if search_query.lower() in row["udvalg"].lower()]
            if filtered:
                st.write("Fundne udvalg:")
                for row in filtered:
                    if st.button(row['udvalg'], key=f"search_select_{row['id']}"):
                        st.session_state.checked_nodes = [row['id']]
                        expanded_nodes = []
                        current_node = row['id']
                        while current_node is not None:
                            expanded_nodes.append(current_node)
                            parent_node = next((r['overordnetudvalg'] for r in rows if r['id'] == current_node), None)
                            current_node = parent_node
                        st.session_state.expanded_nodes = expanded_nodes
                        st.rerun()
            else:
                st.info("Ingen udvalg matcher søgningen.")

        st.subheader("Send e-mail")
        with db_client.get_connection() as conn:
            # Get all unique roles
            role_query = f"""
            SELECT DISTINCT r.titelkursus as rolle
            FROM {DB_SCHEMA}.personrolle pr
            JOIN {DB_SCHEMA}.rolle r ON pr.rolleid = r.id
            """
            roles = [row['rolle'] for row in conn.execute(text(role_query)).mappings().all() if row['rolle']]

        if roles:
            selected_role = st.selectbox("Vælg rolle", roles, key="role_select")
            if st.button(f"Vis e-mails for alle der er {selected_role}"):
                with db_client.get_connection() as conn:
                    email_query = f"""
                    SELECT p.email
                    FROM {DB_SCHEMA}.personrolle pr
                    JOIN {DB_SCHEMA}.rolle r ON pr.rolleid = r.id
                    JOIN {DB_SCHEMA}.person p ON pr.personid = p.id
                    WHERE r.titelkursus = :selected_role
                    """
                    emails = [row['email'] for row in conn.execute(text(email_query), {"selected_role": selected_role}).mappings().all() if row['email']]
                if emails:
                    if len(emails) < 70:
                        mailto_link = f"mailto:{';'.join(emails)}"
                        st.markdown(
                            f'<a href="{mailto_link}" target="_blank"><button type="button">Send e-mail til alle {selected_role}</button></a>',
                            unsafe_allow_html=True
                        )
                    st.write("; ".join(emails))
                else:
                    st.info("Ingen e-mails fundet for den valgte rolle.")

        if is_admin and edit_mode:
            with st.form("add_udvalg_form", clear_on_submit=True):
                st.subheader("Opret nyt udvalg")
                parent_options = [{"label": row["udvalg"], "value": row["id"]} for row in rows]
                parent_udvalg = st.selectbox(
                    "Overordnet udvalg",
                    options=parent_options,
                    format_func=lambda x: x["label"] if isinstance(x, dict) else str(x),
                    key="parent_udvalg_select"
                ) if parent_options else None

                new_udvalg_name = st.text_input("Navn på nyt udvalg")

                submitted = st.form_submit_button("Opret udvalg")
                if submitted:
                    if not new_udvalg_name.strip():
                        st.warning("Navnet må ikke være tomt.")
                    else:
                        # Check if a udvalg with the same name already exists (case-insensitive)
                        with db_client.get_connection() as conn:
                            check_query = f"""
                            SELECT 1 FROM {DB_SCHEMA}.udvalg WHERE LOWER(udvalg) = :udvalg
                            """
                            exists = conn.execute(
                                text(check_query),
                                {"udvalg": new_udvalg_name.strip().lower()}
                            ).fetchone()
                        if exists:
                            st.warning(f"Et udvalg med navnet '{new_udvalg_name.strip()}' findes allerede.")
                        else:
                            with db_client.get_connection() as conn:
                                insert_query = f"""
                                INSERT INTO {DB_SCHEMA}.udvalg (udvalg, overordnetudvalg)
                                VALUES (:udvalg, :overordnetudvalg)
                                """
                                conn.execute(
                                    text(insert_query),
                                    {
                                        "udvalg": new_udvalg_name.strip(),
                                        "overordnetudvalg": parent_udvalg["value"] if parent_udvalg else None
                                    }
                                )
                                conn.commit()
                            st.session_state.pop("udvalg_data", None)
                            st.session_state.show_add_udvalg_form = False
                            st.session_state.show_success = True
                            st.session_state.success_message = f"Udvalg '{new_udvalg_name.strip()}' er oprettet."
                            st.rerun()
