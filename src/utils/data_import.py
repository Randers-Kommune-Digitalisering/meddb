import io
import pandas as pd
import streamlit as st
import zipfile

from sqlalchemy import text

from utils.config import DB_SCHEMA


def add_extra_features(db_client):
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

                for col_to_drop in ['adgangskode', 'privatemail', 'fagnavn']:  # 'omraade', 'titel'
                    if col_to_drop in dataframe.columns:
                        dataframe = dataframe.drop(columns=[col_to_drop])

                if 'titelkursus' in dataframe.columns:
                    dataframe = dataframe[dataframe['titelkursus'].notna()]

                if 'udvalg' in dataframe.columns:
                    dataframe = dataframe[dataframe['udvalg'].notna()]

                if "email" in dataframe.columns:
                    if "isystem" not in dataframe.columns:
                        dataframe["isystem"] = False

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

    if st.button("Eksporter alle tabeller som CSV"):

        with db_client.get_connection() as conn:
            # Get all table names in the schema
            tables_query = f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{DB_SCHEMA}'
                AND table_type = 'BASE TABLE'
            """
            table_names = [row['table_name'] for row in conn.execute(text(tables_query)).mappings().all()]

            if not table_names:
                st.warning("Ingen tabeller fundet i databasen.")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for table in table_names:
                        df = pd.read_sql(f'SELECT * FROM "{DB_SCHEMA}"."{table}"', conn)
                        csv_buffer = io.StringIO()
                        df.to_csv(csv_buffer, index=False, sep=";")
                        zip_file.writestr(f"{table}.csv", csv_buffer.getvalue())
                zip_buffer.seek(0)
                st.download_button(
                    label="Download alle tabeller (ZIP)",
                    data=zip_buffer,
                    file_name="alle_tabeller.zip",
                    mime="application/zip"
                )


def add_extra_features_new(db_client):
    pass
