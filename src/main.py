import pandas as pd
import streamlit as st
import numpy as np
import altair as alt

# from utils.database import DatabaseClient # Uncomment when using database
# from utils.config import DB_HOST, DB_USER, DB_PASS, DB_NAME # Uncomment when using database

# db_client = DatabaseClient(db_type="mssql" ,database=DB_NAME, username=DB_USER, password=DB_PASS, host=DB_HOST) # Uncomment when using database

pd.set_option('display.max_columns', None)
st.set_page_config(page_title="Streamlit-Template", layout="wide")
st.title("Streamlit-Template")
chart_tab, csv_tab = st.tabs(
    ["Template til grafer", "Fra CSV til Charts"]
)

with chart_tab:
    st.write("Template til at lave grafer i Streamlit")
    np.random.seed(42)
    data = pd.DataFrame({
        'Day': np.arange(1, 101),
        'Product A': np.random.randint(50, 100, size=100),
        'Product B': np.random.randint(30, 80, size=100),
        'Product C': np.random.randint(20, 70, size=100)
    })

    data_long = data.melt('Day', var_name='Product', value_name='Sales')

    line_chart = alt.Chart(data_long).mark_line().encode(
        x=alt.X('Day', title='Day'),
        y=alt.Y('Sales', title='Sales'),
        color='Product',
        tooltip=['Day', 'Product', 'Sales']
    )
    st.altair_chart(line_chart, use_container_width=True)

    bar_chart = alt.Chart(data_long).mark_bar().encode(
        x=alt.X('Day', title='Day'),
        y=alt.Y('Sales', title='Sales'),
        color='Product',
        tooltip=['Day', 'Product', 'Sales']
    )
    st.altair_chart(bar_chart, use_container_width=True)

    area_chart = alt.Chart(data_long).mark_area().encode(
        x=alt.X('Day', title='Day'),
        y=alt.Y('Sales', title='Sales'),
        color='Product',
        tooltip=['Day', 'Product', 'Sales']
    )
    st.altair_chart(area_chart, use_container_width=True)

with csv_tab:
    csv_df = pd.read_csv('template.csv', sep=';')
    csv_df = csv_df[['Device']]
    device_counts = csv_df['Device'].value_counts().reset_index()
    device_counts.columns = ['Device', 'Count']
    top_8_devices = device_counts.nlargest(5, 'Count')

    chart_col, table_col = st.columns(2)
    with chart_col:
        st.write("## Top 5 Devices")
        device_chart = alt.Chart(top_8_devices).mark_bar().encode(
            x=alt.X('Device', title='Device'),
            y=alt.Y('Count', title='Number of devices'),
            color=alt.Color('Device'),
            tooltip=[alt.Tooltip('Device'), alt.Tooltip('Count')]
        ).properties(
            width=600, height=400)
        st.altair_chart(device_chart, use_container_width=True)
