import pandas as pd
from io import BytesIO
import streamlit as st
import streamlit_antd_components as sac
from streamlit_keycloak import login
from streamlit_tree_select import tree_select

from delta import DeltaClient
from utils.config import KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID, XFLOW_URL, PRIORITY_MEMBERS
from meddb_data import MeddbData
from school_data import SchoolData
from forms import create_form, edit_name_form, delete_form, change_committee_type_form, move_committee_form, create_commmittee_form, create_union_form, edit_union_form

delta_client = DeltaClient()
meddb = MeddbData()
schooldb = SchoolData()


st.set_page_config(page_title="MED-Database", page_icon="🗄️", layout="wide")
st.markdown('<style>table {width:100%;}</style>', unsafe_allow_html=True)

# State
committee_tree, parent_map, node_map = meddb.get_committee_tree()

if "checked_nodes" not in st.session_state:
    st.session_state.checked_nodes = []

if "expanded_nodes" not in st.session_state:
    st.session_state.expanded_nodes = []

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
            st.markdown(f"Logget ind med: {email} - Du har ingen redigeringsrettigheder. Anmod [her]({XFLOW_URL})")

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
            st.session_state.expanded_nodes = []

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
                        username = st.text_input("Brugernavn")
                        name = st.text_input("Navn")
                        email = st.text_input("E-mail")

                        search = st.form_submit_button("Søg")
                        if search:
                            if not username and not name and not email:
                                st.error("Indtast mindst ét søgekriterie: brugernavn, navn eller e-mail.")
                                st.stop()
                            res = delta_client.search(search_name=name, email=email, username=username)
                            school_res = schooldb.search_person(username=username, name=name, email=email)
                            res.extend(school_res)
                            st.session_state.people_search = res

                        clear_search = st.form_submit_button("Nulstil søgning", disabled=not res)
                        if clear_search:
                            st.session_state.people_search = []
                            st.rerun()
                    if res:
                        role_options = [(r.id, r.name) for r in meddb.get_all_roles()]
                        role_values = [opt[0] for opt in role_options]

                        union_options = [(None, "Ingen")] + [(u.id, u.name) for u in meddb.get_all_unions()]
                        union_values = [opt[0] for opt in union_options]

                        expand = True if len(res) == 1 else False
                        for r in res:
                            with st.expander(r['Navn'], expanded=expand):
                                with st.form(f"add_member_form_{r['Navn']}_{r['Afdeling']}", clear_on_submit=True):
                                    top_line = '| ' + ' | '.join(['Navn', 'Afdeling']) + ' |' + '\n| ' + ' | '.join(['---'] * 2) + ' |' + '\n| ' + ' | '.join([r['Navn'], r['Afdeling']]) + ' |'
                                    buttom_line = '| ' + ' | '.join(['Brugernavn', 'E-mail']) + ' |' + '\n| ' + ' | '.join(['---'] * 2) + ' |' + '\n| ' + ' | '.join([r['Brugernavn'], r['E-mail']]) + ' |'
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
        memberships = meddb.get_committee_members(selected_node['value'])
        emails = [m.person.email for m in memberships if m.person.email]
        if emails:
            mailto_link = f"mailto:{';'.join(emails)}"
            st.markdown(
                f'<a href="{mailto_link}" target="_blank"><button type="button">Send e-mail til alle i udvalg</button></a>',
                unsafe_allow_html=True
            )

        def get_priority(role):
            return PRIORITY_MEMBERS.index(role) if role in PRIORITY_MEMBERS else len(PRIORITY_MEMBERS)

        sorted_rows = sorted(
            memberships,
            key=lambda x: (get_priority(x.role.name), x.role.name, x.person.name)
        )

        cols = st.columns([2, 2, 2, 1]) if user_roles and st.session_state.get("editing", False) else st.columns([2, 2, 2])
        cols[0].markdown("<span style='font-size:1.2em; font-weight:bold;'>Navn</span>", unsafe_allow_html=True)
        cols[1].markdown("<span style='font-size:1.2em; font-weight:bold;'>Rolle</span>", unsafe_allow_html=True)
        cols[2].markdown("<span style='font-size:1.2em; font-weight:bold;'>Email</span>", unsafe_allow_html=True)
        if user_roles and st.session_state.get("editing", False):
            cols[3].write(' ')

        for i, m in enumerate(sorted_rows):
            cols = st.columns([2, 2, 2, 1]) if user_roles and st.session_state.get("editing", False) else st.columns([2, 2, 2])
            cols[0].markdown(f"<span>{m.person.name}</span>", unsafe_allow_html=True)
            cols[1].markdown(f"<span>{m.role.name}</span>", unsafe_allow_html=True)
            if not m.person.found_in_system:
                email_link = f'<span>{m.person.email} ❌</span>'
            else:
                email_link = f'<span>{m.person.email}</span>'
            cols[2].markdown(email_link, unsafe_allow_html=True)
            # Admin - remove member button
            if 'edit_member' in user_roles and st.session_state.get("editing", False):
                if cols[3].button("Fjern", key=f"slet_{m.person.name}_{m.role.name}_{m.person.email}"):
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
        def flatten_nodes(committee_tree):
            flat = []
            for node in committee_tree:
                flat.append(node)
                if node.get("children"):
                    flat.extend(flatten_nodes(node["children"]))
            return flat

        flat_nodes = flatten_nodes(committee_tree)
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

                    st.session_state.expanded_nodes = expanded_nodes
                    st.rerun()
        else:
            st.info("Ingen udvalg matcher søgningen.")

    # Data export section
    st.subheader("Dataudtræk")
    with st.expander("Udtræk for personer ikke i systemet"):
        persons = meddb.get_persons_not_in_system()
        mapped_persons = []
        for p in persons:
            roles = list({m.role.name for m in p.committee_memberships if m.role})
            mapped_persons.append({
                "Navn": p.name,
                "Email": p.email,
                "Org. Enhed": p.organization,
                "Roller": ", ".join(roles) if roles else None
            })

        if mapped_persons:
            df = pd.DataFrame(mapped_persons)
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)
            st.download_button(
                label="Download som Excel",
                data=excel_buffer,
                file_name="meddb_ikke_i_systemet.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Alle personer findes i systemet.")

    with st.expander("Udtræk baseret på roller"):
        role_options = [(role.id, role.name) for role in meddb.get_all_roles()]
        role_values = [opt[0] for opt in role_options]

        if role_options:
            selected_roles = st.multiselect(
                "Vælg rolle(r)",
                options=role_values,
                format_func=lambda x: next(label for val, label in role_options if val == x),
                key="role_select"
            )
            if selected_roles:
                all_with_roles = meddb.get_persons_by_roles(ids=selected_roles)
                if all_with_roles:
                    mapped_persons = []
                    for p in all_with_roles:
                        roles = list({m.role.name for m in p.committee_memberships if m.role and m.role.id in selected_roles})
                        mapped_persons.append({
                            "Navn": p.name,
                            "Email": p.email,
                            "Org. Enhed": p.organization,
                            "Roller": ", ".join(roles) if roles else None
                        })
                    df = pd.DataFrame(mapped_persons)
                    excel_buffer = BytesIO()
                    df.to_excel(excel_buffer, index=False)
                    excel_buffer.seek(0)
                    selected_roles_str = "_".join([label for val, label in role_options if val in selected_roles])
                    st.download_button(
                        label="Download som Excel",
                        data=excel_buffer,
                        file_name=f"meddb_{selected_roles_str}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("Ingen fundet for den valgte rolle.")

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
                create_commmittee_form(
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
