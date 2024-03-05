import streamlit as st


uploaded_file = st.file_uploader("Upload a file", type=["csv", "txt"])

api_key = st.text_input("Enter the API key:")

