import streamlit as st
import requests
import pandas as pd
from urllib.parse import urlparse
import os
from collections import Counter

# Constants and Configurations
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

# Function Definitions
# Assuming all your function definitions here (e.g., get_serp_data, load_domain_info, etc.)

# Streamlit UI components setup
st.set_page_config(layout="wide")
uploaded_file = st.file_uploader("Upload a file", type=["xlsx"], help="Upload the Excel file if Domains aren't tagged correctly")
SERP_API_KEY = st.text_input("Enter the API key:", "", help="Enter your SERP API key. You can find this in your SERP API dashboard.")

# Allow multiple queries input
queries_input = st.text_area("Enter up to 5 search queries, separated by a newline:", "", help="Enter the search terms you want to analyze, one per line. Example: 'best online casinos\nonline gambling sites'.")
queries = queries_input.strip().split('\n')[:5]

location = st.selectbox("Select location:", ["los angeles, california, united states", "houston, texas, united states", "denver, colorado, united states", "milwaukee, wisconsin, united states", "baltimore, maryland, united states", "kansas city, missouri, united states", "indianapolis, indiana, united states", "nashville, tennessee, united states", "boston, massachusetts, united states", "phoenix, arizona, united states", "seattle, washington, united states", "virginia beach, virginia, united states", "newark, new jersey, united states", "detroit, michigan, united states", "charlotte, north carolina, united states", "atlanta, georgia, united states", "columbus, ohio, united states", "chicago, illinois, united states", "philadelphia, pennsylvania, united states", "new york city, new york, united states", "jacksonville, florida, united states"])
gl = st.selectbox("Select country code:", ["us", "ca", "au"])
device = st.selectbox("Select device:", ["desktop", "tablet", "mobile"])

if uploaded_file is not None:
    EXCEL_PATH = os.getcwd() + "/src/serprating.xlsx"
    if os.path.exists(EXCEL_PATH):
        os.remove(EXCEL_PATH)
    with open(EXCEL_PATH, "wb") as file:
        file.write(uploaded_file.getvalue())
else:
    EXCEL_PATH = os.getcwd() + '/src/serpratingtest.xlsx'

if queries and SERP_API_KEY:
    if st.button("Calculate SERP Rating Scores"):
        col1, col2 = st.columns(2)
        current_col = 0
        
        domain_info_df = load_domain_info(EXCEL_PATH)

        for query in queries:
            query = query.strip()
            if query:
                with (col1 if current_col % 2 == 0 else col2):
                    st.subheader(f"Results for: {query}")
                    serp_data = get_serp_data(query, location, gl, device)
                    organic_results = serp_data.get('organic_results', [])
                    classified_organic_results = classify_urls(organic_results, domain_info_df)

                    # Overview Analysis
                    regulations = [result['Regulation'] for result in classified_organic_results]
                    classes = [result['Class'] for result in classified_organic_results]
                    
                    regulation_counts = Counter(regulations)
                    total_regulations = sum(regulation_counts.values())
                    regulation_percentages = {reg: (count / total_regulations * 100) for reg, count in regulation_counts.items()}
                    
                    class_counts = Counter(classes)
                    
                    regulation_df = pd.DataFrame(list(regulation_percentages.items()), columns=['Regulation', 'Percentage'])
                    regulation_df['Percentage'] = regulation_df['Percentage'].apply(lambda x: f"{x:.2f}%")
                    
                    class_ratios_df = pd.DataFrame(list(class_counts.items()), columns=['Class', 'Count'])
                    
                    st.markdown("### Regulation Overview")
                    st.dataframe(regulation_df.style.hide_index())
                    
                    st.markdown("### Class Ratios")
                    st.dataframe(class_ratios_df.style.hide_index())

                    final_results = assign_numbers_and_calculate_transformed(classified_organic_results)
                    sections_info = extract_links_and_count_sections(serp_data)
                    serp_rating_score = calculate_serp_rating(final_results, sections_info) * 2
                    cliq_kd = (serp_rating_score - 41.2) / (101.3 - 41.2) * 100
                    cliq_kd_color_message = get_cliQ_kd_color_message(cliq_kd)
                    st.markdown(f"CliQ KD for '{query}' in {location}: {cliq_kd_color_message}", unsafe_allow_html=True)

                    # Summary Section
                    with st.expander("See Detailed Results", expanded=False):
                        st.markdown("### Top Organic Results")
                        results_df = pd.DataFrame(final_results[:10], columns=['Position', 'link', 'Regulation', 'Class'])
                        results_df.rename(columns={'link': 'URL'}, inplace=True)
                        st.dataframe(results_df)

                        st.markdown("### SERP Features Overview")
                        for section, info in sections_info.items():
                            display_label = LABEL_MAPPING.get(section, section.capitalize())
                            st.markdown(f"**{display_label} Count:** {info['count']}")
                            if info["links"]:
                                st.markdown(f"**{display_label} Links:**")
                                for link in info["links"]:
                                    st.markdown(f"- {link}")

                current_col += 1
