import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Data Test", layout="wide")
st.title("Data Load Test")

DATA_DIR = "data"

if not os.path.exists(DATA_DIR):
    st.error("data folder not found")
    st.stop()

st.write("Files in data folder:", os.listdir(DATA_DIR))

for filename in ["entities.csv", "transactions.csv", "events.csv", "links.csv"]:
    path = os.path.join(DATA_DIR, filename)

    if not os.path.exists(path):
        st.warning(f"{filename} missing")
        continue

    try:
        df = pd.read_csv(path)
        st.success(f"{filename}: {len(df)} rows")
        st.dataframe(df.head(10), use_container_width=True)
    except Exception as e:
        st.error(f"Error reading {filename}: {e}")