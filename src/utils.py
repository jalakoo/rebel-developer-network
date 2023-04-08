import streamlit as st
import csv
import requests

@st.cache_data
def list_from_csv(url, column_name):
    response = requests.get(url)
    lines = response.text.strip().split('\n')
    reader = csv.DictReader(lines)
    column_values = [row[column_name] for row in reader]
    return column_values