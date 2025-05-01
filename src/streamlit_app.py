import pandas as pd
import streamlit as st
from streamlit_keycloak import login
from streamlit_tree_select import tree_select

from sqlalchemy import text
from main import SCHEMA, db_client
from utils.config import KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID


st.set_page_config(page_title="MED-Database", page_icon="🗄️", layout="wide")
st.markdown('<style>table {width:100%;}</style>', unsafe_allow_html=True)


# Fetch rows from the database only once
if "udvalg_data" not in st.session_state:
    with db_client.get_connection() as conn:
        try:
            query = 'SELECT id, overordnetudvalg, udvalg FROM meddb.udvalg'
            result = conn.execute(text(query))
            st.session_state.udvalg_data = result.mappings().all()  # Store rows as dictionaries in session state
        except Exception as e:
            st.error(f"Error fetching data from the database: {e}")
            st.session_state.udvalg_data = None

if "checked_nodes" not in st.session_state:
    st.session_state.checked_nodes = []

if "expanded_nodes" not in st.session_state:
    st.session_state.expanded_nodes = []


keycloak = login(
    url=KEYCLOAK_URL,
    realm=KEYCLOAK_REALM,
    client_id=KEYCLOAK_CLIENT_ID
)

if keycloak.authenticated:
    email = keycloak.user_info['email'].lower()
    with db_client.get_connection() as conn:
        query = f"SELECT 1 FROM {SCHEMA}.administratorer WHERE LOWER(email) = :email"
        result = conn.execute(text(query), {"email": email}).fetchone()
        is_admin = result is not None
    if is_admin:
        st.write(f"{keycloak.user_info['name']} er logget ind som administrator")
    else:
        st.write(f"{keycloak.user_info['name']} er logget ind som bruger")
else:
    email = None


if email == 'rune.aagaard.keena@randers.dk':

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

                columns = []
                for col_name, dtype in zip(dataframe.columns, dataframe.dtypes):
                    if col_name == "id":
                        columns.append(f"{col_name} INTEGER PRIMARY KEY")  # Define as INTEGER PRIMARY KEY
                    elif col_name.endswith("Id"):
                        columns.append(f"{col_name} INTEGER")  # Assuming foreign keys are integers
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
                CREATE TABLE IF NOT EXISTS {SCHEMA}.{table_name} (
                    {', '.join(columns)}
                )
                """

                conn.execute(text(create_table_query))
                conn.commit()

                # Add foreign key constraints for columns ending with "Id"
                for col_name in dataframe.columns:
                    if col_name.endswith("Id") and col_name != "id":
                        referenced_table = col_name[:-2].lower()  # Remove "Id" to get the referenced table name
                        if referenced_table == "fag":
                            referenced_table = "fagforening"
                        add_foreign_key_query = f"""
                        ALTER TABLE {SCHEMA}.{table_name}
                        ADD CONSTRAINT fk_{table_name}_{col_name}
                        FOREIGN KEY ({col_name})
                        REFERENCES {SCHEMA}.{referenced_table}(Id)
                        ON DELETE CASCADE
                        """
                        conn.execute(text(add_foreign_key_query))
                        conn.commit()

                # Insert the data into the table
                dataframe.to_sql(table_name, conn, if_exists="append", index=False, schema=SCHEMA)

                st.success(f"The table '{table_name}' has been created successfully.")
                conn.commit()
        else:
            st.error("File name is not valid. Please use a file name with only one dot.")
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            tables = [row['table_name'] for row in result]
            st.write("Tables in the database:", tables)


# Use the cached data to build the tree structure
rows = st.session_state.udvalg_data

if rows:

    # Convert rows into a dictionary for tree structure
    nodes = []
    row_dict = {row['id']: {'label': row['udvalg'], 'value': row['id']} for row in rows}

    # Build the tree structure
    for row in rows:
        parent_id = row['overordnetudvalg']
        if parent_id is None and row['udvalg'] == 'HOVEDUDVALG':  # Not right - but some 'deleted'? udvalg are still there with no parent
            # Top-level node
            nodes.append(row_dict[row['id']])
        else:
            # Add as a child to its parent
            if parent_id in row_dict:
                if 'children' not in row_dict[parent_id]:
                    row_dict[parent_id]['children'] = []
                row_dict[parent_id]['children'].append(row_dict[row['id']])

    # Create two columns for layout
    col1, col2 = st.columns([1, 2])

    # Display the tree in the left column
    with col1:
        # Rerender the tree with updated checked nodes
        selected = tree_select(
            nodes,
            no_cascade=True,
            expanded=st.session_state.expanded_nodes,  # Default expanded nodes
            checked=st.session_state.checked_nodes  # Use session state for checked nodes
        )

        if selected:
            new_checked_nodes = selected.get("checked", [])
            if len(new_checked_nodes) == 2:
                # Take the value not in the session state
                new_checked_nodes = [node for node in new_checked_nodes if node not in st.session_state.checked_nodes]

            if len(new_checked_nodes) == 1:
                expanded_nodes = []
                current_node = int(new_checked_nodes[0])
                while current_node is not None:
                    expanded_nodes.append(current_node)
                    parent_node = next((row['overordnetudvalg'] for row in rows if row['id'] == current_node), None)
                    current_node = parent_node

                st.session_state.expanded_nodes = expanded_nodes

            # If a new node is selected, update the session state
            if len(new_checked_nodes) == 1 and new_checked_nodes != st.session_state.checked_nodes:
                st.session_state.checked_nodes = new_checked_nodes  # Update to the new selection
                st.rerun()  # Rerun the app to reflect the new selection

            # If two nodes are selected, keep only the newest one
            if len(new_checked_nodes) == 2:
                st.session_state.checked_nodes = [new_checked_nodes[-1]]  # Keep the last selected node
                st.rerun()

            # If more than two nodes are selected, show a warning and reset
            if len(new_checked_nodes) > 2:
                st.warning("Multiple nodes selected. Resetting selection...")
                st.session_state.checked_nodes = []  # Clear the checked nodes
                st.rerun()

    # Display the selected 'udvalg' in the right column
    with col2:
        if st.session_state.checked_nodes:
            # Ensure only one node is selected
            item = st.session_state.checked_nodes[0]
            selected_node = row_dict.get(int(item), {})
            if selected_node:
                st.header(selected_node.get('label', 'Unknown'))
                with db_client.get_connection() as conn:
                    query = f"""
                    SELECT p.navn, r.titelkursus as rolle, p.email
                    FROM {SCHEMA}.personrolle pr
                    JOIN {SCHEMA}.rolle r ON pr.rolleid = r.id
                    JOIN {SCHEMA}.person p ON pr.personid = p.id
                    WHERE pr.udvalgsid = :udvalgsid
                    """
                    result = conn.execute(text(query), {"udvalgsid": selected_node['value']})
                    roles_and_persons = result.mappings().all()

                # Display the result in a DataFrame
                df = pd.DataFrame(roles_and_persons)
                if not df.empty:
                    df = df[['navn', 'rolle', 'email']]
                    # Capitalize column names
                    df.columns = [col.capitalize() for col in df.columns]

                    # Sort the dataframe to prioritize specific roles
                    priority_roles = ['Formand', 'Næstformand', 'Sekretær', 'Udvalgsadministrator']
                    df['Priority'] = df['Rolle'].apply(lambda x: priority_roles.index(x) if x in priority_roles else len(priority_roles))
                    df = df.sort_values(by=['Priority', 'Rolle', 'Navn']).drop(columns=['Priority'])

                    # Convert email values to hyperlinks
                    df['Email'] = df['Email'].apply(lambda x: f'<a href="mailto:{x}">{x}</a>')

                    st.write(df.style.hide(axis="index").set_properties(**{'text-align': 'left'}).to_html(escape=False), unsafe_allow_html=True)
                else:
                    st.write("Ingen personer fundet på det valgte udvalg.")
            else:
                st.error("Selected node not found.")
        else:
            st.write("No udvalg selected.")
