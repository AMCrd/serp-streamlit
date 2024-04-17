import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlparse
import os
import base64
from io import BytesIO

# Constants and Configuration
SERP_BASE_URL = "https://serpapi.com/search"
POSITION_MULTIPLIERS = {
    1: 5, 2: 4, 3: 3, 4: 1.5, 5: 1.4,
    6: 1.3, 7: 1.2, 8: 1.1, 9: 1.05, 10: 1.05,
}
ALTERNATIVE_POSITION_MULTIPLIERS = POSITION_MULTIPLIERS
LABEL_MAPPING = {
    "ads": "Sponsored Ads",
    "related_questions": "People Also Ask",
    "answer_box": "Answer Box",
    "discussions_and_forums": "Discussion and Forums",
    "knowledge_graph": "Knowledge Graph"
}

def get_cliQ_kd_color_message(cliQ_kd):
    if 0 <= cliQ_kd <= 20:
        color = "green"
    elif 21 <= cliQ_kd <= 40:
        color = "lightgreen"
    elif 41 <= cliQ_kd <= 60:
        color = "yellow"
    elif 61 <= cliQ_kd <= 80:
        color = "orange"
    elif 81 <= cliQ_kd <= 100:
        color = "red"
    else:
        color = "white"  
    return f"<span style='color: {color}; font-size: 24px;'>{cliQ_kd:.2f}</span>"

def get_serp_data(query, location, gl, device):
    params = {
        "api_key": SERP_API_KEY,
        "engine": "google",
        "q": query,
        "location": location,
        "hl": "en",
        "gl": gl,
        "device": device,
        "num": 20,
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
        domain = urlparse(result['link']).netloc.lower().replace('www.', '')
        matching_info = domain_info_df[domain_info_df['Domain'] == domain]
        if not matching_info.empty:
            result['Regulation'] = matching_info.iloc[0]['Regulation']
            result['Class'] = matching_info.iloc[0]['Class']
        else:
            result['Regulation'] = 'Other'
            result['Class'] = 'Other'
    return organic_results

def assign_numbers_and_calculate_transformed(final_results):
    class_to_number = {"Publisher": 1, "Parasite": 2, "UGC": 2, "Operator": 2, "News": 2, "Apps": 2, "Social": 2, "Other": 1}
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
    if sections_info['ads']['count'] == 0:
        current_multipliers = ALTERNATIVE_POSITION_MULTIPLIERS
    else:
        current_multipliers = POSITION_MULTIPLIERS
    
    serp_rating = sum([
        sections_info['ads']['count'] * 2,
        sections_info['related_questions']['count'] * 1.05,
        sections_info['answer_box']['count'] * 1,
        sections_info['discussions_and_forums']['count'] * 1.05,
        sections_info['knowledge_graph']['count'] * 1
    ])
    
    for result in final_results[:10]:
        position = result['position']
        transformed_value = result['Transformed']
        multiplier = current_multipliers.get(position, 1)
        serp_rating += transformed_value * multiplier
    
    return serp_rating

# Functions to handle download links
def to_excel(df):
    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Sheet1', index=False)
            writer.save()
            processed_data = output.getvalue()
        return processed_data
    except Exception as e:
        st.error(f"Error in generating Excel file: {str(e)}")
        return None

def get_table_download_link(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="table.csv">Download CSV</a>'
    return href

def get_excel_download_link(df):
    val = to_excel(df)
    b64 = base64.b64encode(val).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="table.xlsx">Download Excel</a>'
    return href

# Streamlit UI components setup
st.set_page_config(layout="wide")
uploaded_file = st.file_uploader("Upload a file", type=["xlsx"], help="Upload the Excel file if Domains aren't tagged correctly")
SERP_API_KEY = st.text_input("Enter the API key:", "", help="Enter your SERP API key. You can find this in your SERP API dashboard.")

# Allow multiple queries input up to 5 - all using the same regional parameter
queries_input = st.text_area("Enter up to 5 search queries, separated by a newline:", "", help="Enter the search terms you want to analyze, one per line. Example: 'best online casinos\nonline gambling sites'.")
queries = queries_input.strip().split('\n')[:5]  # Split by newline and take up to 5 queries

location = st.selectbox("Select location:", ["los angeles, california, united states", "houston, texas, united states", "denver, colorado, united states", "milwaukee, wisconsin, united states", "baltimore, maryland, united states", "kansas city, missouri, united states", "indianapolis, indiana, united states", "nashville, tennessee, united states", "boston, massachusetts, united states", "phoenix, arizona, united states", "seattle, washington, united states", "virginia beach, virginia, united states", "newark, new jersey, united states", "detroit, michigan, united states", "charlotte, north carolina, united states", "atlanta, georgia, united states", "columbus, ohio, united states", "chicago, illinois, united states", "philadelphia, pennsylvania, united states", "new york city, new york, united states", "jacksonville, florida, united states"], help="Select the location for your search. Example: 'Los Angeles, California, United States'")
gl = st.selectbox("Select country code:", ["us", "ca", "au"], help="Select the 2-letter country code. Example: 'US' for the United States.")
device = st.selectbox("Select device:", ["desktop", "tablet", "mobile"], help="Choose the type of device to simulate the search on. This affects how search results are fetched.")

if uploaded_file is not None:
    EXCEL_PATH = os.getcwd() + "/src/serprating.xlsx"
    if os.path.exists(EXCEL_PATH):
        os.remove(EXCEL_PATH)
    with open(EXCEL_PATH, "wb") as file:
        file.write(uploaded_file.getvalue())
else:
    EXCEL_PATH = os.getcwd() + '/src/serpratingtest.xlsx'

# Continue from the previous function, assuming previous sections remain unchanged
if queries and SERP_API_KEY:
    if st.button("Calculate SERP Rating Scores"):
        col1, col2 = st.columns(2)  # Defines two columns for the layout
        current_col = 0  # Helps alternate between columns
        
        for query in queries:
            query = query.strip()  # Trim whitespace
            if query:  # Check if the query is not empty
                # Alternate columns for each keyword's output
                with (col1 if current_col % 2 == 0 else col2):
                    st.subheader(f"Results for: {query}")
                    serp_data = get_serp_data(query, location, gl, device)
                    organic_results = serp_data.get('organic_results', [])

                    domain_info_df = load_domain_info(EXCEL_PATH)
                    classified_organic_results = classify_urls(organic_results, domain_info_df)
                    final_results = assign_numbers_and_calculate_transformed(classified_organic_results)

                    sections_info = extract_links_and_count_sections(serp_data)
                    serp_rating_score = calculate_serp_rating(final_results, sections_info) * 2

                    # Scaling SERP Rating Score to CliQ KD
                    cliq_kd = (serp_rating_score - 41.2) / (101.3 - 41.2) * 100

                    # Display CliQ KD color based on range
                    cliq_kd_color_message = get_cliQ_kd_color_message(cliq_kd)
                    st.markdown(f"CliQ KD for '{query}' in {location}: {cliq_kd_color_message}", unsafe_allow_html=True)
                    
                    # Summary Section
                    with st.expander("See summary", expanded=False):
                        # Displaying organic results 
                        all_results = []
                        for result in final_results[:10]:
                            all_results.append({
                                "Position": result['position'], 
                                "URL": result.get('link', 'URL not available'), 
                                "Regulation": result['Regulation'],
                                "Class": result['Class']
                            })
                        results_table = pd.DataFrame(all_results)
                        markdown_table = "Position | URL | Regulation | Class\n--- | --- | --- | ---\n"
                        for _, row in results_table.iterrows():
                            markdown_table += f"{row['Position']} | [{row['URL']}]({row['URL']}) | {row['Regulation']} | {row['Class']}\n"
                        st.markdown(markdown_table, unsafe_allow_html=True)
                        
                        # Download links
                        st.markdown(get_table_download_link(results_table), unsafe_allow_html=True)
                        st.markdown(get_excel_download_link(results_table), unsafe_allow_html=True)

                        # Enhanced Counts and Links Display
                        st.subheader("Ads and SERP Features:")
                        for section, info in sections_info.items():
                            display_label = LABEL_MAPPING.get(section, section.capitalize())
                            st.markdown(f"**{display_label} Count:** {info['count']}")
                            if info["links"]:
                                st.markdown(f"**{display_label} Links:**")
                                for link in info["links"]:
                                    st.markdown(f"- [{link}]({link})", unsafe_allow_html=True)

                current_col += 1  # Move to the next column for the next keyword

