import pandas as pd
import streamlit as st
import streamlit_antd_components as sac
from io import BytesIO
from streamlit_keycloak import login
from streamlit_tree_select import tree_select

from delta import DeltaClient
from meddb_data import MeddbData
from models import CommitteeMembership
from school_data import SchoolData
from forms import create_form, edit_name_form, delete_form, change_committee_type_form, move_committee_form, create_committee_form, create_union_form, edit_union_form
from utils.database import DatabaseClient
from utils.config import KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID, XFLOW_URL, PRIORITY_MEMBERS, DB_HOST, DB_USER, DB_PASS, DB_NAME, DB_PORT, DB_SCHEMA, SKOLE_AD_DB_SCHEMA


@st.cache_resource
def get_delta_client():
    return DeltaClient()


@st.cache_resource
def get_db_client():
    return DatabaseClient(
        db_type="postgresql",
        database=DB_NAME,
        username=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )


@st.cache_resource
def get_meddb(_db_client):
    return MeddbData(db_client=_db_client, schema=DB_SCHEMA)


@st.cache_resource
def get_schooldb(_db_client):
    return SchoolData(db_client=_db_client, schema=SKOLE_AD_DB_SCHEMA)


delta_client = get_delta_client()
db_client = get_db_client()
meddb = get_meddb(db_client)
schooldb = get_schooldb(db_client)


st.set_page_config(page_title="MED-Database", page_icon="🗄️", layout="wide", initial_sidebar_state="expanded")
st.markdown('<style>table {width:100%;}</style>', unsafe_allow_html=True)
st.markdown(
    """
    <style>
    /* Make the resizable sidebar wider */
    [data-testid="stSidebar"] {
        width: 310px !important;          /* your desired width */
        min-width: 310px !important;      /* ensures drag-resize starts at this width */
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# State
committee_tree, parent_map, node_map = meddb.get_committee_tree()

if "checked_nodes" not in st.session_state:
    st.session_state.checked_nodes = []

if "expanded_nodes" not in st.session_state:
    st.session_state.expanded_nodes = [1]

if "show_success" not in st.session_state:
    st.session_state.show_success = False

edit_mode = st.session_state.get("editing", False)

# Authentication
keycloak = login(
    url=KEYCLOAK_URL,
    realm=KEYCLOAK_REALM,
    client_id=KEYCLOAK_CLIENT_ID
)

user_roles = []

if keycloak.authenticated:
    email = keycloak.user_info.get('email', None)
    if email:
        email = email.lower()

        user_roles = keycloak.user_info.get('resource_access', {}).get(KEYCLOAK_CLIENT_ID, {}).get('roles', [])

        if 'edit_member' in user_roles and 'edit_udvalg' in user_roles:
            st.write(f"Logget ind med: {email} - Du kan tilføje/fjerne medlemmer og administrere udvalg")
        elif 'edit_member' in user_roles:
            st.write(f"Logget ind med: {email} - Du kan tilføje/fjerne medlemmer")
        elif 'edit_udvalg' in user_roles:
            st.write(f"Logget ind med: {email} - Du kan administrere udvalg")
        else:
            st.write(f"Logget ind med: {email} - Du har ingen redigeringsrettigheder.")

        st.markdown(f"Anmod om redigeringsrettigheder [her]({XFLOW_URL})")

    else:
        st.error("Ingen e-mail fundet i brugeroplysningerne.")

if user_roles:
    if user_roles and st.session_state.get("editing", False):
        st.markdown("<span style='font-size:2em; color:red; font-weight:bold;'>Du er ved at redigere</span>", unsafe_allow_html=True)
    if st.button("Rediger" if not edit_mode else "Afslut redigering", key="toggle_editing"):
        st.session_state.editing = not edit_mode
        st.rerun()

# Menu - Committee selection
with st.sidebar:
    st.subheader("Udvalg")
    selected = tree_select(
        committee_tree,
        no_cascade=True,
        expanded=st.session_state.expanded_nodes,
        checked=st.session_state.checked_nodes
    )

    if selected:
        new_checked_nodes = selected.get("checked", [])

        try:
            new_checked_nodes = [int(v) for v in new_checked_nodes]
        except Exception:
            pass

        if len(new_checked_nodes) == 0:
            st.session_state.checked_nodes = []
            st.session_state.expanded_nodes = [1]  # Reset to root (HOVEDUDVALG)

        if len(new_checked_nodes) == 2:
            new_checked_nodes = [
                node for node in new_checked_nodes
                if node not in st.session_state.checked_nodes
            ]

        if len(new_checked_nodes) == 1:
            expanded_nodes = []
            current_node = new_checked_nodes[0]
            while current_node is not None:
                expanded_nodes.append(current_node)
                current_node = parent_map.get(current_node)

            expanded_nodes = expanded_nodes or [1]  # Reset to root (HOVEDUDVALG)
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

# Message control
if st.session_state.get("show_success", False):
    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.success(st.session_state.get("success_message", " "))
        if st.button("OK"):
            st.session_state.show_success = False
            st.session_state.success_message = ""
            st.rerun()
    st.stop()

# Committee selected - show details
elif st.session_state.checked_nodes:
    item = st.session_state.checked_nodes[0]
    selected_node = node_map.get(int(item), {})
    if selected_node:
        st.header(selected_node.get('label', 'Ukendt'))
        st.write(selected_node.get('className') if selected_node.get('className') is not None else 'Ukendt')

        if user_roles and st.session_state.get("editing", False):
            tabs_items = []
            if 'edit_member' in user_roles:
                tabs_items.append(sac.TabsItem(label='Medlemmer'))
            if 'edit_udvalg' in user_roles:
                tabs_items.append(sac.TabsItem(label='Udvalg'))

            default_tab = st.session_state.get("selected_edit_tab", tabs_items[0].label if tabs_items else None)
            tabs = sac.tabs(
                items=tabs_items,
                align='center',
                use_container_width=True,
                index=[item.label for item in tabs_items].index(default_tab) if default_tab and tabs_items else 0
            )

            st.session_state["selected_edit_tab"] = tabs

            # Admin section - search and add members
            if user_roles and st.session_state.get("editing", False):
                if 'edit_member' in user_roles and tabs == 'Medlemmer':
                    res = st.session_state.get("people_search", [])
                    st.subheader("Tilføj medlem")
                    with st.form("search_form", clear_on_submit=True):
                        name = st.text_input("Navn")
                        email = st.text_input("E-mail")

                        search = st.form_submit_button("Søg")
                        if search:
                            if not name and not email:
                                st.error("Indtast mindst ét søgekriterie: navn eller e-mail.")
                                st.stop()
                            res = delta_client.search(search_name=name, email=email)
                            school_res = schooldb.search_person(name=name, email=email)
                            res.extend(school_res)
                            st.session_state.people_search = res

                        clear_search = st.form_submit_button("Nulstil søgning", disabled=not res)
                        if clear_search:
                            st.session_state.people_search = []
                            st.rerun()
                    if res:
                        role_options = [(None, "Ingen")] + [(r.id, r.name) for r in meddb.get_all_roles()]
                        role_values = [opt[0] for opt in role_options]

                        union_options = [(None, "Ingen")] + [(u.id, u.name) for u in meddb.get_all_unions()]
                        union_values = [opt[0] for opt in union_options]

                        expand = True if len(res) == 1 else False
                        for r in res:
                            with st.expander(r['Navn'], expanded=expand):
                                with st.form(f"add_member_form_{r['Navn']}_{r['Afdeling']}", clear_on_submit=True):
                                    top_line = '| ' + ' | '.join(['Navn', 'Afdeling']) + ' |' + '\n| ' + ' | '.join(['---'] * 2) + ' |' + '\n| ' + ' | '.join([r['Navn'], r['Afdeling']]) + ' |'
                                    buttom_line = '| E-mail |' + '\n| --- |' + '\n| ' + r['E-mail'] + ' |'
                                    st.markdown(top_line)
                                    st.markdown(buttom_line)
                                    role = st.selectbox(
                                        "Rolle",
                                        options=role_values,
                                        format_func=lambda x: next(label for val, label in role_options if val == x),
                                        key=f"role_{r['Navn']}_{r['Afdeling']}"
                                    )
                                    union = st.selectbox(
                                        "Fagforening",
                                        options=union_values,
                                        format_func=lambda x: next(label for val, label in union_options if val == x),
                                        key=f"union_{r['Navn']}_{r['Afdeling']}"
                                    )
                                    add_btn = st.form_submit_button("Tilføj")
                                    if add_btn:
                                        if role is None:
                                            st.error("Vælg en rolle for medlemmet.")
                                        else:
                                            person = meddb.add_or_update_person(name=r['Navn'], email=r['E-mail'], username=r['Brugernavn'], organization=r['Afdeling'], union_id=union)
                                            committee_membership = meddb.create_committee_member(person_id=person.id, committee_id=selected_node['value'], role_id=role)
                                            st.session_state.success_message = (f"{person.name} er tilføjet som {committee_membership.role.name} til {selected_node['label']}.")
                                            st.session_state.show_success = True
                                            st.rerun()

                # Admin section - edit current committee
                if 'edit_udvalg' in user_roles and tabs == 'Udvalg':
                    top_left, top_right = st.columns(2)
                    bottom_left, bottom_right = st.columns(2)
                    with top_left:
                        st.subheader("Omdøb udvalg")
                        edit_name_form(
                            type_name="udvalg",
                            get_all_func=lambda: [meddb.get_committee_by_id(selected_node['value'])],
                            update_func=meddb.update_committee,
                            hide_selectbox=True
                        )
                    with top_right:
                        st.subheader("Skift type")
                        current_udvalg_id = selected_node['value']
                        change_committee_type_form(
                            current_id=current_udvalg_id,
                            get_current_func=meddb.get_committee_by_id,
                            get_all_types_func=meddb.get_all_committee_types,
                            update_func=meddb.update_committee
                        )
                    with bottom_left:
                        st.subheader("Flyt udvalg")
                        current_id = selected_node['value']
                        current_label = selected_node['label']
                        current_parent_id = parent_map.get(current_id)
                        current_parent_label = node_map[current_parent_id]["label"] if current_parent_id and current_parent_id in node_map else "Ingen (øverste niveau)"
                        move_committee_form(
                            current_id=current_id,
                            current_label=current_label,
                            current_parent_id=current_parent_id,
                            current_parent_label=current_parent_label,
                            get_all_func=meddb.get_committees,
                            update_func=meddb.update_committee
                        )
                    with bottom_right:
                        st.subheader("Slet udvalg")
                        with st.container(border=True):
                            st.warning(
                                "Advarsel: Sletning af et udvalg vil også slette personers tilknytning til udvalget. "
                                "Denne handling kan ikke fortrydes."
                            )
                            confirm_delete = st.checkbox(f'Jeg bekræfter, at jeg vil slette udvalget "{selected_node.get("label", "")}" permanent.')
                            if confirm_delete and not st.session_state.get("confirm_delete_checked", False):
                                st.session_state["confirm_delete_checked"] = True
                                st.rerun()
                            elif not confirm_delete and st.session_state.get("confirm_delete_checked", False):
                                st.session_state["confirm_delete_checked"] = False
                                st.rerun()
                            delete_form(
                                type_name="udvalg",
                                get_all_func=lambda: [meddb.get_committee_by_id(selected_node['value'])],
                                delete_func=meddb.delete_committee,
                                disabled=not confirm_delete,
                                hide_selectbox=True
                            )
        # Show current members
        include_unions = 'edit_member' in user_roles
        memberships = meddb.get_committee_members(committee_id=selected_node['value'], include_union=include_unions)
        emails = [m.person.email for m in memberships if m.person.email]
        if emails:
            mailto_link = f"mailto:{';'.join(emails)}"
            st.link_button(
                label="Send e-mail til alle i udvalg",
                url=mailto_link,
                use_container_width=False
            )

        def _clean_string(name: str) -> str:
            """Helper function to clean a string for use as a filename and excel sheet name."""
            name[:30] if len(name) > 30 else name
            invalid_chars = r'<>:"/\|?*'
            for ch in invalid_chars:
                name = name.replace(ch, "_")
            return name

        def _generate_members_excel(memberships: list[CommitteeMembership], sheet_name: str) -> bytes:
            """Helper function. Generate an Excel file of committee members with adjusted column widths."""
            def _membership_to_row(membership: CommitteeMembership) -> dict:
                """Helper function to map a CommitteeMembership to a dictionary row."""
                row = {
                    "Navn": membership.person.name,
                    "Email": membership.person.email,
                    "Rolle": membership.role.name,
                    "Org. Enhed": membership.person.organization,
                    "I systemet": "Ja" if membership.person.found_in_system else "Nej"
                }
                if include_unions:
                    row["Fagforening"] = membership.person.union.name if membership.person.union else None
                return row

            df = pd.DataFrame([_membership_to_row(m) for m in memberships])

            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
                worksheet = writer.sheets[sheet_name]
                for idx, col in enumerate(df.columns):
                    # Set width to at least the length of the column name + 2
                    width = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(col)) + 2
                    worksheet.set_column(idx, idx, width)
            buffer.seek(0)
            return buffer.getvalue()

        name = _clean_string(selected_node.get('label', 'Ukendt'))

        st.download_button(
            label="Download som Excel-fil",
            data=_generate_members_excel(
                memberships=memberships,
                sheet_name=name
            ),
            file_name=f"{name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        def _get_priority(role):
            """Helper function to get priority index for a role based on PRIORITY_MEMBERS list."""
            return PRIORITY_MEMBERS.index(role) if role in PRIORITY_MEMBERS else len(PRIORITY_MEMBERS)

        sorted_rows = sorted(
            memberships,
            key=lambda x: (_get_priority(role=x.role.name), x.role.name, x.person.name)
        )

        cols_list = [2, 2, 2, 2, 1] if include_unions and st.session_state.get("editing", False) else [2, 2, 2, 2] if include_unions else [2, 2, 2]

        cols = st.columns(cols_list)
        cols[0].markdown("<span style='font-size:1.2em; font-weight:bold;'>Navn</span>", unsafe_allow_html=True)
        cols[1].markdown("<span style='font-size:1.2em; font-weight:bold;'>Rolle</span>", unsafe_allow_html=True)
        cols[2].markdown("<span style='font-size:1.2em; font-weight:bold;'>Email</span>", unsafe_allow_html=True)
        if include_unions:
            cols[3].markdown("<span style='font-size:1.2em; font-weight:bold;'>Fagforening</span>", unsafe_allow_html=True)
        if include_unions and st.session_state.get("editing", False):
            cols[4].write(' ')

        for i, m in enumerate(sorted_rows):
            cols = st.columns(cols_list)
            cols[0].markdown(f"<span>{m.person.name}</span>", unsafe_allow_html=True)
            cols[1].markdown(f"<span>{m.role.name}</span>", unsafe_allow_html=True)
            if not m.person.found_in_system:
                email_link = f'<span>{m.person.email} ❌</span>'
            else:
                email_link = f'<span>{m.person.email}</span>'
            cols[2].markdown(email_link, unsafe_allow_html=True)
            if include_unions:
                cols[3].markdown(f"<span>{m.person.union.name if m.person.union else ''}</span>", unsafe_allow_html=True)
            # Admin - remove member button
            if 'edit_member' in user_roles and st.session_state.get("editing", False):
                if cols[4].button("Fjern", key=f"slet_{m.person.name}_{m.role.name}_{m.person.email}"):
                    meddb.delete_committee_member(committee_id=m.committee_id, person_id=m.person_id, role_id=m.role_id)
                    st.session_state.show_success = True
                    st.session_state.success_message = f"{m.role.name} {m.person.name} er fjernet fra {selected_node['label']}."
                    st.rerun()
    else:
        st.error("Selected node not found.")

# No committee selected - show search and export options
else:
    st.write("Intet udvalg valgt.")
    st.subheader("Søg udvalg")
    search_query = st.text_input("Søg efter udvalg...", key="udvalg_search")

    if search_query:
        def _flatten_nodes(committee_tree):
            """Helper function to flatten the committee tree into a list."""
            flat = []
            for node in committee_tree:
                flat.append(node)
                if node.get("children"):
                    flat.extend(_flatten_nodes(node["children"]))
            return flat

        flat_nodes = _flatten_nodes(committee_tree=committee_tree)
        filtered = [n for n in flat_nodes if search_query.lower() in n["label"].lower()]

        if filtered:
            st.write("Fundne udvalg:")
            for m in filtered:
                if st.button(m["label"], key=f"search_select_{m['value']}"):
                    # Set checked node
                    st.session_state.checked_nodes = [m["value"]]

                    # Compute expanded path using parent_map
                    expanded_nodes = []
                    current_node = m["value"]
                    while current_node is not None:
                        expanded_nodes.append(current_node)
                        current_node = parent_map.get(current_node)

                    expanded_nodes = expanded_nodes or [1]  # Reset to root (HOVEDUDVALG)
                    st.session_state.expanded_nodes = expanded_nodes
                    st.rerun()
        else:
            st.info("Ingen udvalg matcher søgningen.")

    # Data export section
    if 'edit_udvalg' in user_roles and 'edit_member' in user_roles and not edit_mode:
        st.subheader("Dataudtræk")

        role_options = [(role.id, role.name) for role in meddb.get_all_roles()]
        role_values = [opt[0] for opt in role_options]

        sector_options = [(committee.id, committee.name) for committee in meddb.get_committees_by_parent_id(parent_id=1)]  # Assuming parent_id=1 corresponds to "HOVEDUDVALG" and that all sectors are its children
        sector_values = [opt[0] for opt in sector_options]

        union_options = [(union.id, union.name) for union in meddb.get_all_unions()]
        if union_options:
            union_options.append((None, "Ingen"))
        union_values = [opt[0] for opt in union_options]

        in_system_options = [(None, "Alle"), (True, "I systemet"), (False, "Ikke i systemet")]
        in_system_values = [opt[0] for opt in in_system_options]

        if role_options and sector_options and union_options:
            selected_roles = st.multiselect(
                "Vælg rolle(r)",
                options=role_values,
                format_func=lambda x: next(label for val, label in role_options if val == x),
                key="role_select"
            )
            selected_sectors = st.multiselect(
                "Vælg sektor(er)",
                options=sector_values,
                format_func=lambda x: next(label for val, label in sector_options if val == x),
                key="sector_select"
            )

            include_unions = st.toggle("Inkluder fagforening", value=False, key="include_unions_toggle")

            if include_unions:
                selected_unions = st.multiselect(
                    "Vælg fagforening(er)",
                    options=union_values,
                    format_func=lambda x: next(label for val, label in union_options if val == x),
                    key="union_select"
                )

            selected_in_system = st.selectbox(
                "Findes i systemet",
                options=in_system_values,
                format_func=lambda x: next(label for val, label in in_system_options if val == x),
                key="in_system_select"
            )

            if st.button("Generer udtræk", key="generate_export"):
                with st.spinner("Henter data..."):
                    all_with_roles = meddb.get_persons_by_roles_and_top_committees(role_ids=selected_roles, top_committee_ids=selected_sectors, union_ids=selected_unions if include_unions else None, in_system=selected_in_system)
                    if all_with_roles:
                        mapped_persons = []
                        for p in all_with_roles:
                            roles = list({m.role.name for m in p.committee_memberships if m.role})
                            top_sectors = set()
                            for m in p.committee_memberships:
                                # Skip if no committee or committee is the root (id=1)
                                committee = meddb.get_committee_by_id(m.committee_id)
                                if committee and committee.id != 1:
                                    current = committee
                                    parent_id = current.parent_id
                                    while parent_id and parent_id != 1:
                                        current = meddb.get_committee_by_id(parent_id)
                                        parent_id = current.parent_id
                                    if current.id != 1 and current.name not in top_sectors:
                                        sector_name = current.name
                                        if sector_name.startswith("SEKTOR - "):
                                            sector_name = sector_name.replace("SEKTOR - ", "")
                                        top_sectors.add(sector_name)
                            row = {
                                "Navn": p.name,
                                "Email": p.email,
                                "Org. Enhed": p.organization,
                                "Rolle(r)": ", ".join(roles) if roles else None,
                                "Sektor(er)": ", ".join(list(set(top_sectors))) if top_sectors else None,
                                "I systemet": "Ja" if p.found_in_system else "Nej"
                            }
                            if include_unions:
                                row["Fagforening"] = p.union.name if p.union else None
                            mapped_persons.append(row)
                        df = pd.DataFrame(mapped_persons)
                        excel_buffer = BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                            df.to_excel(writer, index=False, sheet_name="MED data")
                            worksheet = writer.sheets["MED data"]
                            # Set width to at least the length of the column name + 2
                            for idx, col in enumerate(df.columns):
                                width = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(col)) + 2
                                worksheet.set_column(idx, idx, width)
                        excel_buffer.seek(0)
                        st.session_state['excel_buffer'] = excel_buffer.getvalue()
                    else:
                        st.session_state.pop('excel_buffer', None)
                        st.info("Ingen fundet")

        if 'excel_buffer' in st.session_state:
            st.download_button(
                label="Download Excel-fil",
                data=st.session_state['excel_buffer'],
                file_name="MED_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

    # Admin section (Committees, Roles, Unions)
    if 'edit_udvalg' in user_roles and edit_mode:
        st.subheader("Administrer udvalg, roller og fagforeninger")
        tabs_items = ['Udvalg', "Roller", 'Fagforeninger']
        tabs = sac.tabs(
            items=tabs_items,
            align='center',
            use_container_width=True
        )
        if tabs == 'Udvalg':
            with st.expander("Opret nyt udvalg"):
                create_committee_form(
                    get_all_func=meddb.get_committees,
                    get_all_types_func=meddb.get_all_committee_types,
                    create_func=meddb.create_committee
                )
            with st.expander("Opret ny udvalgstype"):
                create_form(type_name='udvalgstype', create_func=meddb.create_committee_type)
            with st.expander("Rediger udvalgstype"):
                edit_name_form(type_name='udvalgstype', get_all_func=meddb.get_all_committee_types, update_func=meddb.update_committee_type)
            with st.expander("Slet udvalgstype"):
                delete_form(type_name='udvalgstype', get_all_func=meddb.get_all_committee_types, delete_func=meddb.delete_committee_type)
        elif tabs == 'Roller':
            create_form(type_name='rolle', create_func=meddb.create_role)
            with st.expander("Rediger rolle"):
                edit_name_form(type_name='Rolle', get_all_func=meddb.get_all_roles, update_func=meddb.update_role)
            with st.expander("Slet rolle"):
                delete_form(type_name='rolle', get_all_func=meddb.get_all_roles, delete_func=meddb.delete_role)
        elif tabs == 'Fagforeninger':
            with st.expander("Opret ny fagforening"):
                create_union_form(create_func=meddb.create_union)
            with st.expander("Rediger fagforening"):
                union_options = [(u.id, u.name) for u in meddb.get_all_unions()]
                union_values = [opt[0] for opt in union_options]
                union_to_edit = st.selectbox(
                    "Vælg fagforening at redigere",
                    options=union_values,
                    format_func=lambda x: next(label for val, label in union_options if val == x),
                    key="edit_union_select"
                )
                if union_to_edit:
                    edit_union_form(
                        id=union_to_edit,
                        get_func=meddb.get_union_by_id,
                        update_func=meddb.update_union
                    )
            with st.expander("Slet fagforening"):
                delete_form(type_name='fagforening', get_all_func=meddb.get_all_unions, delete_func=meddb.delete_union)
