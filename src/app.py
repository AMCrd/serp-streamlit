import streamlit as st
import requests
import pandas as pd
from urllib.parse import urlparse
import os

# Constants and Configurations
SERP_BASE_URL = "https://serpapi.com/search"
LOCATIONS_URL = "https://serpapi.com/locations.json"

# Function to fetch and cache location data from SerpApi
@st.cache
def get_locations(api_key):
    params = {"api_key": api_key}
    response = requests.get(LOCATIONS_URL, params=params)
    response.raise_for_status()
    locations = response.json()
    return {loc['name']: loc['canonical_name'] for loc in locations}

# Function to get SERP data
def get_serp_data(query, location, gl, device, api_key):
    params = {
        "api_key": api_key,
        "engine": "google",
        "q": query,
        "location": location,
        "hl": "en",
        "gl": gl,
        "device": device,
    }
    response = requests.get(SERP_BASE_URL, params=params)
    response.raise_for_status()
    return response.json()

# Function to load domain info from an Excel file
def load_domain_info(excel_path):
    df = pd.read_excel(excel_path, engine='openpyxl')
    df['Domain'] = df['Domain'].str.lower().str.replace('www.', '')
    return df

# Function to classify URLs based on domain info
def classify_urls(organic_results, domain_info_df):
    for result in organic_results:
        if 'link' in result:
            domain = urlparse(result['link']).netloc.lower().replace('www.', '')
            matching_info = domain_info_df[domain_info_df['Domain'] == domain]
            if not matching_info.empty:
                result['Regulation'] = matching_info.iloc[0]['Regulation']
                result['Class'] = matching_info.iloc[0]['Class']
            else:
                result['Regulation'] = 'Other'
                result['Class'] = 'Other'
        else:
            result['Regulation'] = 'Other'
            result['Class'] = 'Other'
    return organic_results

# Function to assign numbers and calculate a transformed value based on class and regulation
def assign_numbers_and_calculate_transformed(final_results):
    class_to_number = {"Publisher": 1, "Operator": 2.5, "News": 2, "App": 2, "Social": 2, "Other": 1}
    regulation_to_number = {"Regulated": 2.5, "Unregulated": 1, "Other": 1}
    for result in final_results:
        result['Class_Num'] = class_to_number.get(result.get('Class', 'Other'), 0)
        result['Regulation_Num'] = regulation_to_number.get(result.get('Regulation', 'Other'), 0)
        result['Transformed'] = (result['Class_Num'] + result['Regulation_Num']) / 2
    return final_results

# Function to extract links and count sections in SERP data
def extract_links_and_count_sections(serp_data):
    sections_info = {
        "ads": {"count": 0, "links": []},
        "related_questions": {"count": 0, "links": []},
        "answer_box": {"count": 0, "links": []},
        "discussions_and_forums": {"count": 0, "links": []},
        "knowledge_graph": {"count": 0, "links": []}
    }
    for section in sections_info:
        if section in serp_data:
            if isinstance(serp_data[section], list):
                for item in serp_data[section]:
                    sections_info[section]["links"].append(item.get("link", "No link"))
                sections_info[section]["count"] = len(sections_info[section]["links"])
            elif isinstance(serp_data[section], dict) and section == "knowledge_graph":
                sections_info[section]["count"] = 1
    return sections_info

# Function to calculate the SERP rating
def calculate_serp_rating(final_results, sections_info, POSITION_MULTIPLIERS):
    serp_rating = sum([
        sections_info['ads']['count'] * 3,
        sections_info['related_questions']['count'] * 1.3,
        sections_info['answer_box']['count'] * 1.3,
        sections_info['discussions_and_forums']['count'] * 1.5,
        sections_info['knowledge_graph']['count'] * 2
    ])
    for result in final_results[:10]:
        position = result['position']
        transformed_value = result['Transformed']
        multiplier = POSITION_MULTIPLIERS.get(position, 1)
        serp_rating += transformed_value * multiplier
    return serp_rating

# Function to get CliQ KD message based on difficulty
def get_cliQ_kd_message(cliQ_kd):
    if 0 <= cliQ_kd <= 20:
        return "Very low difficulty; should highly consider in planning and execution :sunglasses:"
    elif 21 <= cliQ_kd <= 40:
        return "Low difficulty; should consider in planning and execution :grinning:"
    elif 41 <= cliQ_kd <= 60:
        return "Medium difficulty; possible to consider in planning and execution :relieved:"
    elif 61 <= cliQ_kd <= 80:
        return "High difficulty; debatable to consider in planning and execution :neutral_face:"
    elif 81 <= cliQ_kd <= 100:
        return "Very high difficulty; do not consider in planning and execution :unamused:"
    else:
        return "Invalid CliQ KD range"

# Position multipliers for SERP rating calculation
POSITION_MULTIPLIERS = {
    1: 2, 2: 1.9, 3: 1.8, 4: 1.7, 5: 1.5,
    6: 1.2, 7: 1.2, 8: 1.2, 9: 1.1, 10: 1.1,
}

# Streamlit UI
st.title("SERP Rating Tool")

SERP_API_KEY = st.text_input("Enter the SerpApi API key:", "")

if SERP_API_KEY:
    locations_data = get_locations(SERP_API_KEY)

    user_input = st.text_input("Enter your location:")

    # Filter locations based on user input
    filtered_locations = {name: canon for name, canon in locations_data.items() if user_input.lower() in name.lower()}

    # Limit the number of suggestions to prevent overwhelming the user
    max_suggestions = 10
    suggestions = list(filtered_locations.keys())[:max_suggestions]

    if suggestions:
        selected_location = st.selectbox("Did you mean:", options=suggestions)
        canonical_name = filtered_locations[selected_location]
        location = canonical_name
    else:
        st.write("Start typing a location and select from the suggestions.")
        location = ""

    query = st.text_input("Enter your search query: ")
    gl = st.text_input("Enter country code: ")
    device = st.selectbox("Select device:", ["desktop", "tablet", "mobile"])

    uploaded_file = st.file_uploader("Upload a domain information file", type=["xlsx"])

    if st.button("Calculate SERP Rating Score") and query and location and gl and device and uploaded_file:
        # Process the uploaded file
        EXCEL_PATH = os.path.join(st.secrets["TEMP_DIR"], "serprating.xlsx")
        with open(EXCEL_PATH, "wb") as file:
            file.write(uploaded_file.getvalue())

        domain_info_df = load_domain_info(EXCEL_PATH)
        serp_data = get_serp_data(query, location, gl, device, SERP_API_KEY)
        organic_results = serp_data.get('organic_results', [])
        classified_organic_results = classify_urls(organic_results, domain_info_df)
        final_results = assign_numbers_and_calculate_transformed(classified_organic_results)

        sections_info = extract_links_and_count_sections(serp_data)
        serp_rating_score = calculate_serp_rating(final_results, sections_info, POSITION_MULTIPLIERS) * 2

        # Scaling SERP Rating Score to CliQ KD
        cliq_kd = (serp_rating_score - 29.4) / (99.4 - 29.4) * 100

        # Display CliQ KD and message
        st.header(f"CliQ KD for '{query}' in {location}: {cliq_kd:.2f}")
        cliq_kd_message = get_cliQ_kd_message(cliq_kd)
        st.subheader(cliq_kd_message)
else:
    st.write("Please enter your SerpApi API key to start.")
