# TODO: Refactror
# TODO: Hnadle afdeling / omraade
# TODO: Add models and use sqlalchemy ORM
import streamlit as st
import streamlit_antd_components as sac
from streamlit_keycloak import login
from streamlit_tree_select import tree_select

from sqlalchemy import text
from main import DB_SCHEMA, db_client
from delta import DeltaClient
from ms_graph import MSGraphClient
from utils.config import KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID, AD_DB_SCHEMA
from utils.data_import import add_extra_features


delta_client = DeltaClient()
ms_graph_client = MSGraphClient()


st.set_page_config(page_title="MED-Database", page_icon="🗄️", layout="wide")
st.markdown('<style>table {width:100%;}</style>', unsafe_allow_html=True)

# Fetch rows from the database only once
if "udvalg_data_forside" not in st.session_state:
    with db_client.get_connection() as conn:
        try:
            query = 'SELECT id, overordnetudvalg, udvalg, type FROM meddb.udvalg'
            result = conn.execute(text(query))
            st.session_state.udvalg_data_forside = result.mappings().all()
        except Exception as e:
            st.error(f"Error fetching data from the database: {e}")
            st.session_state.udvalg_data_forside = None

if "checked_nodes" not in st.session_state:
    st.session_state.checked_nodes = []

if "expanded_nodes" not in st.session_state:
    st.session_state.expanded_nodes = []

if "show_success" not in st.session_state:
    st.session_state.show_success = False

edit_mode = st.session_state.get("editing", False)

keycloak = login(
    url=KEYCLOAK_URL,
    realm=KEYCLOAK_REALM,
    client_id=KEYCLOAK_CLIENT_ID
)

roles = []

if keycloak.authenticated:
    email = keycloak.user_info.get('email', None)
    if email:
        email = email.lower()

        roles = keycloak.user_info.get('resource_access', {}).get(KEYCLOAK_CLIENT_ID, {}).get('roles', [])

        if 'edit_member' in roles and 'edit_udvalg' in roles:
            st.write(f"Logget ind med: {email} - Du kan tilføje/fjerne medlemmer fra udvalg og redigere udvalg")
        elif 'edit_member' in roles:
            st.write(f"Logget ind med: {email} - Du kan tilføje/fjerne medlemmer fra udvalg")
        elif 'edit_udvalg' in roles:
            st.write(f"Logget ind med: {email} - Du kan redigere udvalg")

        if 'import_export_data' in roles:
            add_extra_features(db_client=db_client)
    else:
        st.error("Ingen e-mail fundet i brugeroplysningerne.")

rows = st.session_state.udvalg_data_forside

if rows:
    nodes = []
    row_dict = {row['id']: {'label': row['udvalg'], 'value': row['id'], 'className': row['type']} for row in rows}

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

    if roles:
        if roles and st.session_state.get("editing", False):
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
            st.write(selected_node.get('className', 'Unknown'))

            if roles and st.session_state.get("editing", False):
                # col_left, col_right = st.tabs(["Medlemmer", "Udvalg"])
                tabs_items = []
                if 'edit_member' in roles:
                    tabs_items.append(sac.TabsItem(label='Medlemmer'))
                if 'edit_udvalg' in roles:
                    tabs_items.append(sac.TabsItem(label='Udvalg'))

                tabs = sac.tabs(
                    items=tabs_items,
                    align='center',
                    use_container_width=True
                )

                if roles and st.session_state.get("editing", False):
                    if 'edit_member' in roles and tabs == 'Medlemmer':
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

                    # with col_right:
                    if 'edit_udvalg' in roles and tabs == 'Udvalg':
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
                                    st.session_state.pop("udvalg_data_forside", None)
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
                                    st.session_state.pop("udvalg_data_forside", None)
                                    st.session_state.show_success = True
                                    st.session_state.success_message = f"Udvalg er omdøbt til '{new_label.strip()}'."
                                    st.rerun()
                        st.subheader("Skift type")
                        with st.form("change_type_form", clear_on_submit=True):
                            current_udvalg_id = selected_node['value']
                            current_type = selected_node.get('className', '')
                            type_options = ['Udvalg', 'Arbejdsmiljøgruppe']
                            default_index = type_options.index(current_type)
                            new_type = st.selectbox(label='Type', options=type_options, index=default_index)
                            type_submitted = st.form_submit_button("Skift")
                            if type_submitted:
                                # if not new_label.strip():
                                #     st.warning("Navnet må ikke være tomt.")
                                if new_type == current_type:
                                    st.info("Typen er uændret.")
                                else:
                                    with db_client.get_connection() as conn:
                                        update_query = f"""
                                        UPDATE {DB_SCHEMA}.udvalg
                                        SET type = :new_type
                                        WHERE id = :udvalg_id
                                        """
                                        conn.execute(
                                            text(update_query),
                                            {"new_type": new_type, "udvalg_id": current_udvalg_id}
                                        )
                                        conn.commit()
                                    st.session_state.pop("udvalg_data_forside", None)
                                    st.session_state.show_success = True
                                    st.session_state.success_message = f"Type er ændret til '{new_type}'."
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
                                st.session_state.pop("udvalg_data_forside", None)
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

                cols = st.columns([2, 2, 2, 1]) if roles and st.session_state.get("editing", False) else st.columns([2, 2, 2])
                cols[0].markdown("<span style='font-size:1.2em; font-weight:bold;'>Navn</span>", unsafe_allow_html=True)
                cols[1].markdown("<span style='font-size:1.2em; font-weight:bold;'>Rolle</span>", unsafe_allow_html=True)
                cols[2].markdown("<span style='font-size:1.2em; font-weight:bold;'>Email</span>", unsafe_allow_html=True)
                if roles and st.session_state.get("editing", False):
                    cols[3].write(' ')

                for i, row in enumerate(sorted_rows):
                    cols = st.columns([2, 2, 2, 1]) if roles and st.session_state.get("editing", False) else st.columns([2, 2, 2])
                    cols[0].markdown(f"<span>{row['navn']}</span>", unsafe_allow_html=True)
                    cols[1].markdown(f"<span>{row['rolle']}</span>", unsafe_allow_html=True)
                    if not row.get("isystem"):
                        email_link = f'<span>{row["email"]} ❌</span>'
                    else:
                        email_link = f'<span>{row["email"]}</span>'
                    cols[2].markdown(email_link, unsafe_allow_html=True)
                    if 'edit_member' in roles and st.session_state.get("editing", False):
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

        if roles and edit_mode:
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
                            st.session_state.pop("udvalg_data_forside", None)
                            st.session_state.show_add_udvalg_form = False
                            st.session_state.show_success = True
                            st.session_state.success_message = f"Udvalg '{new_udvalg_name.strip()}' er oprettet."
                            st.rerun()
