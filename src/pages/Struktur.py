import streamlit as st

from sqlalchemy import text
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.layouts import TreeLayout
from streamlit_flow.state import StreamlitFlowState

from main import db_client

st.set_page_config(page_title="MED-Database", page_icon="🗄️", layout="wide")

styles = {'Udfyldning': {'color': 'white', 'backgroundColor': '<color>', 'border': 'none', 'fontFamily': 'Arial', 'padding': 2, 'width': '110px'}, 'Ingen Udfyldning': {'color': 'black', 'backgroundColor': 'white', 'border': '2px solid <color>', 'fontFamily': 'Arial', 'padding': 2, 'width': '110px'}}
available_colors = {'Blå': '#20347c', 'Rød': '#991325', 'Skygge Grøn': '#a0c4bc', 'Grøn': '#70b42c', 'Orange': '#f88414', 'Grå': '#7c7a7b'}
udvalg_data = []

with db_client.get_connection() as conn:
    query = 'SELECT id, overordnetudvalg, udvalg, type FROM meddb.udvalg'
    result = conn.execute(text(query))
    udvalg_data = [
        {
            **row,
            'id': int(row['id']) if row['id'] is not None else None,
            'overordnetudvalg': int(row['overordnetudvalg']) if row['overordnetudvalg'] is not None else None
        }
        for row in result.mappings().all()
    ]

    def get_groups(data):
        groups = []
        for item in data:
            if item['udvalg']:
                if '-' in item['udvalg']:
                    parts = item['udvalg'].split('-')
                    if len(parts) > 1:
                        group_name = parts[0].strip()
                        if group_name and group_name not in groups:
                            groups.append(group_name)
        return groups

    def build_hierarchy(data, top_level_id=1, max_depth=2, group_styles=None, direction='down', edge_type='step'):
        nodes = []
        edges = []

        input_direction = direction if direction in ['right'] else 'bottom'
        output_direction = 'left' if direction in ['right'] else 'top'
        for item in data:
            node_id = item['id']
            parent_id = item['overordnetudvalg']

            if item.get('udvalg', None):
                color = group_styles['colors'].get('Ingen gruppe', available_colors['Grå'])
                for group, group_color in (group_styles['colors'] or {}).items():
                    if group in item['udvalg']:
                        color = group_color
                        break
                style = group_styles['styles'].get('Ingen gruppe', styles['Ingen Udfyldning'])
                for group, group_style in (group_styles['styles'] or {}).items():
                    if group in item['udvalg']:
                        style = group_style
                        break

            if node_id == top_level_id:
                style = {k: (v.replace('<color>', color) if isinstance(v, str) else v) for k, v in style.items()}
                style.update({'fontSize': '12px'})
                nodes.append(StreamlitFlowNode(pos=(0, 0), id=str(node_id), node_type='input', source_position=input_direction, data={'content': item['udvalg']}, style=style))
            elif parent_id is None:
                pass
            else:
                if max_depth is not None:
                    depth = 1
                    current_parent = parent_id
                    is_descendant = False
                    while current_parent is not None:
                        if current_parent == top_level_id:
                            is_descendant = True
                            break
                        parent_item = next((x for x in data if x['id'] == current_parent), None)
                        if parent_item:
                            current_parent = parent_item['overordnetudvalg']
                            depth += 1
                        else:
                            break
                    if is_descendant and depth <= max_depth:
                        style = {k: (v.replace('<color>', color) if isinstance(v, str) else v) for k, v in style.items()}
                        style.update({'fontSize': '10px'})
                        nodes.append(StreamlitFlowNode(pos=(0, 0), id=str(node_id), source_position=input_direction, target_position=output_direction, data={'content': item['udvalg']}, style=style))
                        edges.append(StreamlitFlowEdge(id=str(node_id), source=str(parent_id), target=str(node_id), edge_type=edge_type, style={'stroke': color, 'strokeWidth': 2, 'strokeDasharray': '15,5'}))

        source_ids = {edge.source for edge in edges}
        for node in nodes:
            if node.id not in source_ids and node.type != 'input':
                node.type = 'output'

        return nodes, edges

with st.expander('Lav Struktur Diagram', expanded=True):
    with st.form("hierarchy_form"):
        top_cols = st.columns(4)
        with top_cols[0]:
            top_level_nodes = [item for item in udvalg_data if (item['overordnetudvalg'] == 1 or item['overordnetudvalg'] is None)]
            top_node = st.selectbox(
                "Vælg topniveau",
                options=[{"label": item['udvalg'], "id": item['id']} for item in top_level_nodes],
                format_func=lambda x: x["label"],
                index=0
            )["id"]

        with top_cols[1]:
            level = st.selectbox("Vælg antal niveauer", list(range(0, 5)), index=0)

        with top_cols[2]:
            direction_map = {"Ned": "down", "Højre": "right"}
            direction_label = st.selectbox(
                "Retning",
                options=list(direction_map.keys()),
                index=0
            )
            direction = direction_map[direction_label]

        with top_cols[3]:
            edge_type_map = {
                "Standard": "default",
                "Trin": "step",
                "Trin (jævn)": "smoothstep",
                "Lige": "straight"
            }
            edge_type_label = st.selectbox(
                "Kant type",
                options=list(edge_type_map.keys()),
                index=0
            )
            edge_type = edge_type_map[edge_type_label]

        group_styles = {'colors': {}, 'styles': {}}
        groups = get_groups(udvalg_data)
        groups.append("Ingen gruppe")
        cols = st.columns(3)
        for idx, group in enumerate(groups):
            with cols[idx % 3]:
                st.write(f"Vælg farve og stil for gruppen '{group}'")
                col_color, col_style = st.columns(2)
                with col_color:
                    color = st.selectbox(
                        "farve",
                        list(available_colors.keys()),
                        index=idx % len(available_colors),
                        key=f"group_color_{group}"
                    )
                    group_styles['colors'][group] = available_colors[color]
                with col_style:
                    style = st.selectbox(
                        "stil",
                        list(styles.keys()),
                        index=0,
                        key=f"group_style_{group}"
                    )
                    group_styles['styles'][group] = styles[style]

        submitted = st.form_submit_button("Lav nyt diagram", disabled=not udvalg_data)

if submitted:
    st.write(level)
    filtered_nodes, filtered_edges = build_hierarchy(udvalg_data, top_level_id=top_node, max_depth=level, group_styles=group_styles, direction=direction, edge_type=edge_type)
    st.session_state.flow_state = StreamlitFlowState(filtered_nodes, filtered_edges)

if 'flow_state' not in st.session_state:
    st.session_state.flow_state = StreamlitFlowState([], [])

streamlit_flow('struktur', st.session_state.flow_state, fit_view=True, height=600, show_minimap=True, show_controls=True, hide_watermark=True, layout=TreeLayout(direction=direction))
