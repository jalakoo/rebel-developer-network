import streamlit as st
import streamlit.components.v1 as components
from streamlit_chat import message
from neo4j_driver import execute_query
import openai
from train_cypher import examples
from utils import list_from_csv
from constants import STAR_WARS_SYSTEMS

# Config
openai.api_key = st.secrets['OPENAI_KEY']
st.set_page_config(layout="wide")

# Functions
@st.cache_data
def programming_languages_list():
    return list_from_csv("http://gist.githubusercontent.com/jalakoo/1199236143eeb6b85c8146db7ea2d925/raw/0178f18b3ce360017d84790b6bffaf18fd7c15d1/programming_languages.csv", "language")

@st.cache_data
def star_wars_systems():
    system_names = [s['Planet'] for s in STAR_WARS_SYSTEMS]
    return system_names

def find_developers(
    team_size: int,
    req_skills: list[str],
    base: str,
    distance: int,
    reb_affinity: float
) -> list[str]:
    query = f"""
    MATCH (t:Topic)<-[r:KNOWS]-(p:Person)-[f:FROM]->(s:System), (o:System)-[d:CONNECTED_TO*1..{distance}]->(o2:System)
    WHERE t.name in $req_skills AND o2.name = $base AND o.name = s.name
    RETURN DISTINCT p.name as name, s.name as homeworld LIMIT $team_size
"""
    params = {
        'req_skills': req_skills,
        'base': base,
        'team_size': team_size
    }
    records = execute_query(query, params)
    if records is None:
        return []
    
    result = []
    for r in records:
        result.append({
            'name': r.get('name'),
            'homeworld': r.get('homeworld')
        })
    return result


# UI
# Convulted way to center image
col1, col2, col3 = st.columns([1,1,1])
with col1:
    st.write('')
    # TODO: Animations? More data?
with col2:
    st.image('./media/hack_it.png')
with col3:
    st.write('')
    # TODO: Animations? More data?

# st.title("Rebel Developers Network")
# st.markdown("<h1 style='text-align: center; color: white;'>Rebel Developers Network</h1>", unsafe_allow_html=True)

t1, t2 = st.tabs(["Dashboard", " Search"])
with t1:
    # Building mode
    components.iframe("http://neodash.graphapp.io/", height=1000, scrolling=False)

    # TODO:
    # View only mode

with t2:
    with st.expander("Advanced Options"):
        team_size = st.slider("Team Size", 1, 12, 6)
        req_skills = st.multiselect("Required programming skills", programming_languages_list())

        t2c1, t2c2 = st.columns([1,1])
        with t2c1:
            base = st.selectbox("Location of Rebel Development Base", star_wars_systems())
        with t2c2:
            distance = st.slider("Max Hyperspace Jumps from Base", 1, 25, 5)

        reb_affinity = st.select_slider("Political Affinity", ["Imperial", "Imperial Sympathetic", "Neutral", "Rebel Sympathetic", "Rebel"], value = "Neutral")
    
    # TODO:
    if st.button("Find Rebel Developers"):
        developers = find_developers(
            team_size, 
            req_skills, 
            base, 
            distance, 
            reb_affinity)
        # Display suggested rebel developers
        st.json(developers)

# Using ChatGPT like search
# with t2:

#     def generate_response(prompt):
#         completions = openai.Completion.create(
#             engine="text-davinci-003",
#             prompt=examples + "\n#" + prompt,
#             max_tokens=1000,
#             n=1,
#             stop=None,
#             temperature=0.5,
#         )
#         cypher_query = completions.choices[0].text
#         message = execute_query(cypher_query)
#         return message, cypher_query


#     # Storing the chat
#     if 'generated' not in st.session_state:
#         st.session_state['generated'] = []

#     if 'past' not in st.session_state:
#         st.session_state['past'] = []


#     # Streamlit UI
#     col1, col2 = st.columns([2, 1])

#     with col2:
#         # Generated Cypher
#         another_placeholder = st.empty()
#     with col1:
#         # Chat
#         placeholder = st.empty()

#     # User questions
#     # TODO: Follow up questions?
#     user_input = st.text_input("Welcome, how may I assist you?", "", key="input")
#     if user_input:
#             output, cypher_query = generate_response(user_input)
#             # TODO: How to handle empty responses?
#             # store the output
#             st.session_state.past.append(user_input)
#             st.session_state.generated.append((output, cypher_query))

#     # Message placeholder
#     with placeholder.container():
#         if st.session_state['generated']:
#             message(st.session_state['past'][-1],
#                     is_user=True, key=str(-1) + '_user')
#             for j, text in enumerate(st.session_state['generated'][-1][0]):
#                 message(text, key=str(-1) + str(j))

#     # Generated Cypher statements
#     with another_placeholder.container():
#         if st.session_state['generated']:
#             st.text_area("Generated Cypher statement",
#                         st.session_state['generated'][-1][1], height=240)
