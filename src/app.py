import streamlit as st
import requests
import pandas as pd
from urllib.parse import urlparse
import os

# Constants and Configurations
SERP_BASE_URL = "https://serpapi.com/search"

POSITION_MULTIPLIERS = {
    1: 2, 2: 1.9, 3: 1.8, 4: 1.7, 5: 1.5,
    6: 1.2, 7: 1.2, 8: 1.2, 9: 1.1, 10: 1.1,
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


# Retrieve SERP data
def get_serp_data(query, location, gl):
    params = {
        "api_key": SERP_API_KEY,
        "engine": "google",
        "q": query,
        "location": location,
        "hl": "en",
        "gl": gl,
    }
    response = requests.get(SERP_BASE_URL, params=params)
    response.raise_for_status()
    return response.json()

# Load domain information from Excel
def load_domain_info(excel_path):
    df = pd.read_excel(excel_path, engine='openpyxl')
    df['Domain'] = df['Domain'].str.lower().str.replace('www.', '')
    return df

# Classify URLs
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

# Assign numbers and calculate transformed values
def assign_numbers_and_calculate_transformed(final_results):
    class_to_number = {"Publisher": 1, "Operator": 2.5, "News": 2, "App": 2, "Social": 2, "Other": 1}
    regulation_to_number = {"Regulated": 2.5, "Unregulated": 1, "Other": 1}
    for result in final_results:
        result['Class_Num'] = class_to_number.get(result.get('Class', 'Other'), 0)
        result['Regulation_Num'] = regulation_to_number.get(result.get('Regulation', 'Other'), 0)
        result['Transformed'] = (result['Class_Num'] + result['Regulation_Num']) / 2
    return final_results

# Extract links and count sections
def extract_links_and_count_sections(serp_data):
    sections_info = {
        "ads": {"count": 0, "links": []},
        "related_questions": {"count": 0, "links": []},
        "answer_box": {"count": 0, "links": []}
    }
    # Extracting ads links
    for ad in serp_data.get("ads", []):
        sections_info["ads"]["links"].append(ad.get("link", "No link"))
    sections_info["ads"]["count"] = len(sections_info["ads"]["links"])
    
    # Extracting related questions links
    for question in serp_data.get("related_questions", []):
        sections_info["related_questions"]["links"].append(question.get("link", "No link"))
    sections_info["related_questions"]["count"] = len(sections_info["related_questions"]["links"])
    
    # Extracting answer box link
    if serp_data.get("answer_box"):
        sections_info["answer_box"]["links"].append(serp_data.get("answer_box", {}).get("link", "No link"))
        sections_info["answer_box"]["count"] = 1

    return sections_info

# Adjusted calculate_serp_rating function
def calculate_serp_rating(final_results, sections_info):
    serp_rating = sum([
        sections_info['ads']['count'] * 3,
        sections_info['related_questions']['count'] * 1.3,
        sections_info['answer_box']['count'] * 1.3
    ])
    for result in final_results[:10]:
        position = result['position']
        transformed_value = result['Transformed']
        multiplier = POSITION_MULTIPLIERS.get(position, 1)
        serp_rating += transformed_value * multiplier
    return serp_rating


uploaded_file = st.file_uploader("Upload a file", type=["xlsx"])
SERP_API_KEY = st.text_input("Enter the API key:", "")
query = st.text_input("Enter your search query: ", "")
location = st.text_input("Enter location: ")
gl = st.text_input("Enter country code: ")

if uploaded_file is not None:
    # Define the file path
    EXCEL_PATH = os.getcwd() + "/src/serprating.xlsx"

    # Check if the file already exists
    if os.path.exists(EXCEL_PATH):
        os.remove(EXCEL_PATH)  # Remove the existing file

    # Save the uploaded file as "serprating.xlsx"
    with open(EXCEL_PATH, "wb") as file:
        file.write(uploaded_file.getvalue())
else:
    EXCEL_PATH = os.getcwd() + '/src/serpratingtest.xlsx'

if query != "" and SERP_API_KEY != "":
    if st.button("Calculate SERP Rating Score"):
        serp_data = get_serp_data(query, location, gl)
        organic_results = serp_data.get('organic_results', [])

        domain_info_df = load_domain_info(EXCEL_PATH)
        classified_organic_results = classify_urls(organic_results, domain_info_df)
        final_results = assign_numbers_and_calculate_transformed(classified_organic_results)

        sections_info = extract_links_and_count_sections(serp_data)
        serp_rating_score = calculate_serp_rating(final_results, sections_info) * 2


        # Scaling SERP Rating Score to CliQ KD
        cliq_kd = (serp_rating_score - 29.4) / (99.4 - 29.4) * 100

        # Cliq kd output
        st.header(f"CliQ KD for :blue['{query}'] in {location}: {cliq_kd:.2f}")
        
        # Determine and display the CliQ KD message
        cliq_kd_message = get_cliQ_kd_message(cliq_kd)
        st.subheader(cliq_kd_message)
        
        st.divider()
        
        st.header("Summary")
    with st.expander("See summary"):
        
        # Displaying the first 10 organic results with their details
        st.subheader("\nFOrganic Results:")
        all_results = []
        for result in final_results[:10]:
            all_results.append({"Position":result['position'], "URL": result.get('link', 'URL not available'), 
                    "Regulation": result['Regulation'] ,
                    "Class": result['Class']})
            results_table = pd.DataFrame(all_results)
        st.dataframe(results_table,hide_index=True)
        
        # Displaying counts, links, SERP Rating Score, and CliQ KD
        st.subheader("\nAds and SERP Features:")
        for section, info in sections_info.items():
            st.write(f"\n{section.capitalize()} Count: {info['count']}")
            if info["links"]:
                st.write(f"{section.capitalize()} Links:")
                for link in info["links"]:
                    st.write(f" - {link}")
                        
