import base64
import streamlit as st
import streamlit_antd_components as sac

from collections import defaultdict
from PIL import Image
from io import BytesIO
from sqlalchemy import text
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.layouts import TreeLayout
from streamlit_flow.state import StreamlitFlowState

from main import db_client

st.set_page_config(page_title="MED-Database", page_icon="🗄️", layout="wide")

styles = {'Udfyldning': {'color': 'white', 'backgroundColor': '<color>', 'border': 'none', 'fontFamily': 'Arial', 'padding': 2, 'width': '110px'}, 'Ingen Udfyldning': {'color': 'black', 'backgroundColor': 'white', 'border': '2px solid <color>', 'fontFamily': 'Arial', 'padding': 2, 'width': '110px'}}
available_colors = {'Blå': '#20347c', 'Rød': '#991325', 'Skygge Grøn': '#a0c4bc', 'Grøn': '#70b42c', 'Orange': '#f88414', 'Grå': '#7c7a7b'}


# Helper functions
def custom_sort(item):
    value = item["udvalg"]
    if value.startswith("SEKTOR"):
        return 0
    elif value.startswith("AMG") or value.endswith('AMG'):
        return 2
    else:
        return 1


def build_hierarchy(data, top_level_id=1, max_depth=2, group_styles=None, direction='down', edge_type='step'):
    nodes = []
    edges = []

    level_counts = {}
    max_level = 0

    input_direction = direction if direction in ['right'] else 'bottom'
    output_direction = 'left' if direction in ['right'] else 'top'

    data = sorted(data, key=custom_sort)

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
            nodes.append(StreamlitFlowNode(pos=(0, 0), id=str(node_id), node_type='input', source_position=input_direction, data={'content': f"**{item['udvalg'].strip()}**"}, style=style, draggable=False))
            level_counts[0] = level_counts.get(0, 0) + 1
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
                    style.update({'fontSize': '12px'})
                    nodes.append(StreamlitFlowNode(pos=(0, 0), id=str(node_id), source_position=input_direction, target_position=output_direction, data={'content': f"**{item['udvalg'].strip()}**"}, style=style, draggable=False))
                    edges.append(StreamlitFlowEdge(id=str(node_id), source=str(parent_id), target=str(node_id), edge_type=edge_type, style={'stroke': color, 'strokeWidth': 2, 'strokeDasharray': '15,5'}))
                    level_counts[depth] = level_counts.get(depth, 0) + 1
                    max_level = max(max_level, depth)

    source_ids = {edge.source for edge in edges}
    for node in nodes:
        if node.id not in source_ids and node.type != 'input':
            node.type = 'output'

    max_nodes_on_same_level = max(level_counts.values()) if level_counts else 0
    total_levels = max_level + 1 if level_counts else 1

    return nodes, edges, max_nodes_on_same_level, total_levels


if 'udvalg_data' not in st.session_state:
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

        amg_by_parent = defaultdict(list)
        non_amg = []

        for item in udvalg_data:
            if item['type'] == 'Arbejdsmiljøgruppe':
                amg_by_parent[item['overordnetudvalg']].append(item)
            else:
                non_amg.append(item)

        udvalg_data = []
        for parent, amgs in amg_by_parent.items():
            if len(amgs) == 1:
                udvalg_data.append(amgs[0])
            elif len(amgs) > 1:
                combined = {
                    **amgs[0],
                    'udvalg': f"{len(amgs)} AMG",
                    'id': amgs[0]['id']
                }
                udvalg_data.append(combined)
        udvalg_data.extend(non_amg)

        st.session_state.udvalg_data = udvalg_data

if 'top_udvalg' not in st.session_state:
    top_udvalg = next((u for u in st.session_state.udvalg_data if not u['overordnetudvalg']), None)
    st.session_state.top_udvalg = top_udvalg

if 'important_udvalg' not in st.session_state:
    children_of_top = [u for u in st.session_state.udvalg_data if u["overordnetudvalg"] == st.session_state.top_udvalg['id']]
    parent_ids = {u["overordnetudvalg"] for u in st.session_state.udvalg_data if u["overordnetudvalg"] is not None}
    important_udvalg = sorted([c for c in children_of_top if c["id"] in parent_ids], key=custom_sort)
    st.session_state.important_udvalg = important_udvalg

if 'current_udvalg_id' not in st.session_state:
    st.session_state.current_udvalg_id = None

if 'flow_state' not in st.session_state:
    st.session_state.flow_state = StreamlitFlowState([], [])

if 'screenshot_config' not in st.session_state:
    st.session_state.screenshot_config = {'name': 'diagram', 'addToState': True, 'format': 'png', 'width': 3508, 'height': 1240, 'minZoom': 0.1, 'maxZoom': 2, 'padding': 0.05}


tab_udvalg = [st.session_state.top_udvalg] + st.session_state.important_udvalg
tab_index = sac.tabs([sac.TabsItem(label=u['udvalg'].replace('-', '').strip())for u in tab_udvalg], align='center', size='xm', variant='outline', color='red', use_container_width=True, return_index=True)

if st.session_state.current_udvalg_id != tab_index:
    st.session_state.current_udvalg_id = tab_index
    group_styles = {"colors": {"AMR": "#20347c", "AMG": "#70b42c", "LOM": "#991325", "LMU": "#f88414", "PM": "#f88414", "SEKTOR": "#20347c", "Ingen gruppe": "#7c7a7b"},
                    "styles":
                        {"AMR": {'color': 'black', 'backgroundColor': 'white', 'border': '2px solid <color>', 'fontFamily': 'Arial', 'padding': 2, 'width': '140px'},
                         "AMG": {'color': 'black', 'backgroundColor': 'white', 'border': '2px solid <color>', 'fontFamily': 'Arial', 'padding': 2, 'width': '140px'},
                         "LOM": {'color': 'black', 'backgroundColor': 'white', 'border': '2px solid <color>', 'fontFamily': 'Arial', 'padding': 2, 'width': '140px'},
                         "LMU": {'color': 'black', 'backgroundColor': 'white', 'border': '2px solid <color>', 'fontFamily': 'Arial', 'padding': 2, 'width': '140px'},
                         "PM": {'color': 'black', 'backgroundColor': 'white', 'border': '2px solid <color>', 'fontFamily': 'Arial', 'padding': 2, 'width': '140px'},
                         "SEKTOR": {"color": "white", "backgroundColor": "<color>", "border": "none", "fontFamily": "Arial", "padding": 2, "width": "140px"},
                         "Ingen gruppe": {"color": "white", "backgroundColor": "<color>", "border": "none", "fontFamily": "Arial", "padding": 2, "width": "140px"}}}

    depth = 10
    if tab_udvalg[tab_index]['udvalg'] == 'HOVEDUDVALG':
        depth = 1

    st.session_state.screenshot_config['name'] = tab_udvalg[tab_index]['udvalg']

    filtered_nodes, filtered_edges, nodes_wide, nodes_tall = build_hierarchy(st.session_state.udvalg_data, top_level_id=tab_udvalg[st.session_state.current_udvalg_id]['id'], max_depth=depth, group_styles=group_styles, direction='down', edge_type='smoothstep')

    st.session_state.screenshot_config['width'] = 200 * nodes_wide
    st.session_state.screenshot_config['height'] = 120 * nodes_tall

    st.session_state.flow_state = StreamlitFlowState(filtered_nodes, filtered_edges)

st.write('Tryk på kamera-ikonet øverst til højre for at eksportere grafen')
curr_state = streamlit_flow('flow', st.session_state.flow_state, fit_view=True, height=400, min_zoom=0.1, show_minimap=False, show_controls=True, hide_watermark=True, layout=TreeLayout(direction='down'), pan_on_drag=True, allow_zoom=True, show_screenshot=True, screenshot_config=st.session_state.screenshot_config)

if curr_state.screenshot:
    st.session_state.data_url = curr_state.screenshot

if 'data_url' in st.session_state:
    if st.session_state.data_url:
        data_url = st.session_state.data_url
        header, encoded = data_url.split(",", 1)
        image_data = base64.b64decode(encoded)

        image = Image.open(BytesIO(image_data)).convert("RGB")

        pdf_stream = BytesIO()
        image.save(pdf_stream, format="PDF")
        pdf_stream.seek(0)

        cols = st.columns([2, 1, 1])
        with cols[0]:
            st.image(data_url, caption=f"Forhåndsvisning: {st.session_state.screenshot_config['name']}")

        with cols[1]:
            st.download_button(
                label="Download PNG",
                data=image_data,
                file_name=f"{tab_udvalg[tab_index]['udvalg']}.png",
                mime="image/png"
            )

        with cols[2]:
            st.download_button(
                label="Download PDF",
                data=pdf_stream,
                file_name=f"{tab_udvalg[tab_index]['udvalg']}.pdf",
                mime="application/pdf"
            )
