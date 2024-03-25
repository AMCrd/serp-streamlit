import streamlit as st
import requests
import pandas as pd
from urllib.parse import urlparse
import os

# Constants and Configurations
SERP_BASE_URL = "https://serpapi.com/search"

POSITION_MULTIPLIERS = {
    1: 3.2, 2: 2.5, 3: 2.0, 4: 1.5, 5: 1.4,
    6: 1.3, 7: 1.2, 8: 1.1, 9: 1.05, 10: 1.05,
}

# Alternative POSITION_MULTIPLIERS for cases with 0 ads
ALTERNATIVE_POSITION_MULTIPLIERS = {
    1: 3.2, 2: 2.5, 3: 2.0, 4: 1.5, 5: 1.4,
    6: 1.3, 7: 1.2, 8: 1.1, 9: 1.05, 10: 1.05,
}

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

def get_serp_data(query, location, gl, device):
    params = {
        "api_key": SERP_API_KEY,
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

def load_domain_info(excel_path):
    df = pd.read_excel(excel_path, engine='openpyxl')
    df['Domain'] = df['Domain'].str.lower().str.replace('www.', '')
    return df

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

def assign_numbers_and_calculate_transformed(final_results):
    class_to_number = {"Publisher": 1, "Operator": 2, "News": 2, "Apps": 2, "Social": 2, "Other": 1}
    regulation_to_number = {"Regulated": 2, "Unregulated": 1, "Other": 1}
    for result in final_results:
        result['Class_Num'] = class_to_number.get(result.get('Class', 'Other'), 0)
        result['Regulation_Num'] = regulation_to_number.get(result.get('Regulation', 'Other'), 0)
        result['Transformed'] = (result['Class_Num'] + result['Regulation_Num']) / 2
    return final_results

def extract_links_and_count_sections(serp_data):
    sections_info = {
        "ads": {"count": 0, "links": []},
        "related_questions": {"count": 0, "links": []},
        "answer_box": {"count": 0, "links": []},
        "discussions_and_forums": {"count": 0, "links": []},
        "knowledge_graph": {"count": 0, "links": []}
    }
    # Extracting links and counts
    for section in sections_info:
        if section in serp_data:
            if isinstance(serp_data[section], list):
                for item in serp_data[section]:
                    sections_info[section]["links"].append(item.get("link", "No link"))
                sections_info[section]["count"] = len(sections_info[section]["links"])
            elif isinstance(serp_data[section], dict) and section == "knowledge_graph": 
                sections_info[section]["count"] = 1
    return sections_info

def calculate_serp_rating(final_results, sections_info):
    # Determine which set of POSITION_MULTIPLIERS to use
    if sections_info['ads']['count'] == 0:
        current_multipliers = ALTERNATIVE_POSITION_MULTIPLIERS
    else:
        current_multipliers = POSITION_MULTIPLIERS
    
    serp_rating = sum([
        sections_info['ads']['count'] * 0,
        sections_info['related_questions']['count'] * 1.05,
        sections_info['answer_box']['count'] * 2,
        sections_info['discussions_and_forums']['count'] * 1.05,
        sections_info['knowledge_graph']['count'] * 4
    ])
    
    for result in final_results[:10]:
        position = result['position']
        transformed_value = result['Transformed']
        multiplier = current_multipliers.get(position, 1)  # Use the selected multipliers
        serp_rating += transformed_value * multiplier
    
    return serp_rating

# Streamlit UI components
uploaded_file = st.file_uploader("Upload a file", type=["xlsx"])
SERP_API_KEY = st.text_input("Enter the API key:", "")
query = st.text_input("Enter your search query: ", "")
location = st.selectbox("Select location:", ["los angeles, california, united states", "houston, texas, united states", "denver, colorado, united states", "milwaukee, wisconsin, united states", "baltimore, maryland, united states", "kansas city, missouri, united states", "indianapolis, indiana, united states", "nashville, tennessee, united states", "boston, massachusetts, united states", "phoenix, arizona, united states", "seattle, washington, united states", "virginia beach, virginia, united states", "newark, new jersey, united states", "detroit, michigan, united states", "charlotte, north carolina, united states", "atlanta, georgia, united states", "columbus, ohio, united states", "chicago, illinois, united states", "philadelphia, pennsylvania, united states", "new york city, new york, united states", "jacksonville, florida, united states"])
gl = st.selectbox("Select country code:", ["us", "ca", "au"])
device = st.selectbox("Select device:", ["desktop", "tablet", "mobile"])

if uploaded_file is not None:
    # Define the file path
    EXCEL_PATH = os.getcwd() + "/src/serprating.xlsx"

    # Check if the file already exists
    if os.path.exists(EXCEL_PATH):
        os.remove(EXCEL_PATH)  # Remove the existing file

    # Save the uploaded file
    with open(EXCEL_PATH, "wb") as file:
        file.write(uploaded_file.getvalue())
else:
    EXCEL_PATH = os.getcwd() + '/src/serpratingtest.xlsx'

if query != "" and SERP_API_KEY != "":
    if st.button("Calculate SERP Rating Score"):
        serp_data = get_serp_data(query, location, gl, device)
        organic_results = serp_data.get('organic_results', [])

        domain_info_df = load_domain_info(EXCEL_PATH)
        classified_organic_results = classify_urls(organic_results, domain_info_df)
        final_results = assign_numbers_and_calculate_transformed(classified_organic_results)

        sections_info = extract_links_and_count_sections(serp_data)
        serp_rating_score = calculate_serp_rating(final_results, sections_info) * 2

        # Scaling SERP Rating Score to CliQ KD
        cliq_kd = (serp_rating_score - 41.2) / (113.3 - 41.2) * 100

        # Cliq kd output and message
        st.header(f"CliQ KD for '{query}' in {location}: {cliq_kd:.2f}")
        cliq_kd_message = get_cliQ_kd_message(cliq_kd)
        st.subheader(cliq_kd_message)
        
        st.divider()
        
        # Summary
        st.header("Summary")
        with st.expander("See summary"):
            # Displaying organic results details
            all_results = []
            for result in final_results[:10]:
                all_results.append({
                    "Position": result['position'], 
                    "URL": result.get('link', 'URL not available'), 
                    "Regulation": result['Regulation'],
                    "Class": result['Class']
                })
            results_table = pd.DataFrame(all_results)
            st.dataframe(results_table, hide_index=True)
                
            # Displaying counts and links for ads, SERP features, discussions_and_forums, and knowledge_graph
            st.subheader("Ads and SERP Features:")
            for section, info in sections_info.items():
                st.write(f"{section.capitalize()} Count: {info['count']}")
                if info["links"]:
                    st.write(f"{section.capitalize()} Links:")
                    for link in info["links"]:
                        st.write(f" - {link}")
