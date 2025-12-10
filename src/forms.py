import streamlit as st


# CREATE/ADD forms
def create_form(type_name: str, create_func: callable) -> None:
    """Create a generic form for adding a new item of a given type (e.g., Role, Union)."""
    with st.form(f"add_{type_name.lower()}_form"):
        new_name = st.text_input(f"Navn på ny {type_name.lower()}:")
        submitted = st.form_submit_button("Opret type")
        if submitted:
            if not new_name.strip():
                st.warning("Navnet må ikke være tomt.")
            else:
                create_func(name=new_name.strip())
                st.session_state.show_add_type_form = False
                st.session_state.show_success = True
                st.session_state.success_message = f"{type_name.capitalize()} '{new_name.strip()}' er oprettet."
                st.rerun()


def create_committee_form(get_all_func: callable, get_all_types_func: callable, create_func: callable) -> None:
    """Create a form for adding a new committee."""
    with st.form("add_udvalg_form", clear_on_submit=True):
        parent_options = [(item.id, item.name) for item in get_all_func()]
        parent_options.append((None, "Ingen"))
        parent_values = [opt[0] for opt in parent_options]

        parent_commitee = st.selectbox(
            "Overordnet udvalg",
            options=parent_values,
            format_func=lambda x: next(label for val, label in parent_options if val == x),
            key="parent_udvalg_select"
        )

        new_udvalg_name = st.text_input("Navn på nyt udvalg")

        type_options = [(t.id, t.name) for t in get_all_types_func(include_protected=True)]
        type_values = [opt[0] for opt in type_options]

        committee_type = st.selectbox(
            "Type",
            options=type_values,
            format_func=lambda x: next(label for val, label in type_options if val == x),
            key="new_udvalg_type"
        )

        submitted = st.form_submit_button("Opret udvalg")
        if submitted:
            if not new_udvalg_name.strip():
                st.warning("Navnet må ikke være tomt.")
            else:
                committee = create_func(
                    name=new_udvalg_name.strip(),
                    type_id=committee_type,
                    parent_id=parent_commitee if parent_commitee else None
                )
                st.session_state.show_add_udvalg_form = False
                st.session_state.show_success = True
                st.session_state.success_message = f"Udvalg '{committee.name}' er oprettet."
                st.rerun()


def create_union_form(create_func: callable) -> None:
    """Create a form for adding a new union."""
    with st.form("add_union_form"):
        new_union_name = st.text_input("Navn på ny fagforening")
        new_union_description = st.text_area("Beskrivelse (valgfri)")
        submitted = st.form_submit_button("Opret fagforening")
        if submitted:
            if not new_union_name.strip():
                st.warning("Navnet må ikke være tomt.")
            else:
                union = create_func(name=new_union_name.strip(), description=new_union_description.strip() if new_union_description.strip() else None)
                st.session_state.show_add_union_form = False
                st.session_state.show_success = True
                st.session_state.success_message = f"Fagforening '{union.name}' er oprettet."
                st.rerun()


# EDIT/CHANGE forms
def edit_union_form(id: int, get_func: callable, update_func: callable) -> None:
    """Create a form for editing an existing union."""
    with st.form("edit_union_form"):
        current_union = get_func(id)
        new_union_name = st.text_input("Nyt navn for fagforening", value=current_union.name if current_union else "")
        new_union_description = st.text_area("Ny beskrivelse (valgfri)", value=current_union.description if current_union and current_union.description else "")
        submitted = st.form_submit_button("Opdater fagforening")
        if submitted:
            if not new_union_name.strip():
                st.warning("Navnet må ikke være tomt.")
            elif current_union and new_union_name.strip() == current_union.name and new_union_description.strip() == (current_union.description or ""):
                st.info("Ingen ændringer foretaget.")
            else:
                update_func(id=current_union.id, name=new_union_name.strip(), description=new_union_description.strip() if new_union_description.strip() else None)
                st.session_state.show_success = True
                st.session_state.success_message = f"Fagforening er opdateret til '{new_union_name.strip()}'."
                st.rerun()


def edit_name_form(type_name: str, get_all_func: callable, update_func: callable, hide_selectbox: bool = False) -> None:
    """Create a generic form for editing the name of an item of a given type (e.g., Role, CommitteeType)."""
    with st.form(f"edit_{type_name.lower()}_form"):
        options = [(item.id, item.name) for item in get_all_func()]
        values = [opt[0] for opt in options]
        if hide_selectbox:
            to_edit = values[0] if values else None
        else:
            to_edit = st.selectbox(
                f"Vælg {type_name.lower()} at redigere",
                options=values,
                format_func=lambda x: next(label for val, label in options if val == x),
                key=f"edit_{type_name.lower()}_select"
            )
        current_item = next((item for item in get_all_func() if item.id == to_edit), None)
        new_name = st.text_input("Nyt navn")
        submitted = st.form_submit_button(f"Opdater {type_name.lower()}", disabled=not to_edit)
        if submitted:
            if not new_name.strip():
                st.warning("Navnet må ikke være tomt.")
            elif current_item and new_name.strip() == current_item.name:
                st.info("Navnet er uændret.")
            else:
                update_func(id=to_edit, name=new_name.strip())
                st.session_state.show_success = True
                st.session_state.success_message = f"{type_name.capitalize()} er opdateret til '{new_name.strip()}'."
                st.rerun()


def change_committee_type_form(current_id: int, get_current_func: callable, get_all_types_func: callable, update_func: callable) -> None:
    """Create a form for changing the type of a committee."""
    with st.form("change_type_form", clear_on_submit=True):
        current_committee = get_current_func(current_id)
        current_type_id = current_committee.type_id if current_committee else None

        options = [(item.id, item.name) for item in get_all_types_func(include_protected=True)]
        values = [opt[0] for opt in options]

        new_type_id = st.selectbox(
            label='Type',
            options=values,
            format_func=lambda x: next(label for val, label in options if val == x),
            index=values.index(current_type_id) if current_type_id in values else 0,
            key="edit_current_type_select"
        )
        type_submitted = st.form_submit_button("Skift")
        if type_submitted:
            if new_type_id == current_type_id:
                st.info("Typen er uændret.")
            else:
                update_func(
                    id=current_id,
                    type_id=new_type_id
                )
                st.session_state.show_success = True
                new_type_name = next(label for val, label in options if val == new_type_id)
                st.session_state.success_message = f"Type er ændret til '{new_type_name}'."
                st.rerun()


def move_committee_form(current_id: int, current_label: str, current_parent_id: int, current_parent_label: str, get_all_func: callable, update_func: callable) -> None:
    """Create a form for moving a committee under a different parent committee."""
    with st.form("move_committee_form", clear_on_submit=True):
        st.write(f"Nuværende overordnet udvalg: **{current_parent_label}**")

        if current_id != 1:  # Assuming 1 is the id of HOVEDUDVALG
            options = [(item.id, item.name) for item in get_all_func()]
            options.append((None, "Ingen"))
            values = [opt[0] for opt in options]
            new_parent_id = st.selectbox(
                "Vælg nyt overordnet udvalg",
                options=values,
                format_func=lambda x: next(label for val, label in options if val == x),
                index=values.index(current_parent_id) if current_parent_id in values else 0,
                key="move_parent_select"
            )
        else:
            new_parent_id = None
            st.info(f"Dette udvalg er {current_label} og kan ikke flyttes.")

        submitted = st.form_submit_button("Flyt udvalg")
        if submitted:
            if current_parent_id == new_parent_id:
                st.warning("Vælg et nyt overordnet udvalg.")
            else:
                update_func(
                    id=current_id,
                    parent_id=new_parent_id
                )
                st.session_state.show_success = True
                new_parent_label = next(label for val, label in options if val == new_parent_id) if new_parent_id is not None else "Ingen (øverste niveau)"
                st.session_state.success_message = f"{current_label} er flyttet under {new_parent_label}."
                st.rerun()


# DELETE forms
def delete_form(type_name: str, get_all_func: callable, delete_func: callable, disabled: bool = False, hide_selectbox: bool = False) -> None:
    """Create a generic form for deleting an item of a given type (e.g., Role, Union)."""
    with st.form(f"delete_{type_name.lower()}_form"):
        options = [(item.id, item.name) for item in get_all_func()]
        values = [opt[0] for opt in options]
        if hide_selectbox:
            to_delete = values[0] if values else None
        else:
            to_delete = st.selectbox(
                f"Vælg {type_name.lower()} at slette",
                options=values,
                format_func=lambda x: next(label for val, label in options if val == x),
                key=f"delete_{type_name.lower()}_select"
            )
        submitted = st.form_submit_button(f"Slet {type_name.lower()}", disabled=(to_delete is None or disabled))
        if submitted:
            delete_func(id=to_delete)
            st.session_state.show_success = True
            name = next(label for val, label in options if val == to_delete)
            st.session_state.success_message = f"{type_name.capitalize()} '{name}' er slettet."
            st.rerun()
