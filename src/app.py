import streamlit as st
import streamlit.components.v1 as components
from streamlit_chat import message
from neo4j_driver import execute_query
import openai
from train_cypher import examples
from utils import list_from_csv
from constants import STAR_WARS_SYSTEMS
from models import Person, System
import random
import datetime

# Config
# openai.api_key = st.secrets['OPENAI_KEY']
DEFAULT_TIME_CUTOFF = st.secrets['DEFAULT_TIME_CUTOFF_MINUTES']
st.set_page_config(layout="wide")

# Functions
@st.cache_data
def programming_languages_list():
    return list_from_csv("http://gist.githubusercontent.com/jalakoo/1199236143eeb6b85c8146db7ea2d925/raw/0178f18b3ce360017d84790b6bffaf18fd7c15d1/programming_languages.csv", "language")

@st.cache_data
def star_wars_systems():
    system_names = [s['Planet'] for s in STAR_WARS_SYSTEMS]
    return system_names

@st.cache_data
def possible_rebel_systems(minimum_rebel_affinity: float= 0.5):
    query = f"""
MATCH (s:System)
WHERE ANY (affinity IN s.rebel_affinity WHERE affinity > {minimum_rebel_affinity})
RETURN DISTINCT s
    """
    systems = execute_query(query)
    result = []
    for r in systems:
        s = r.get('s')
        new_system = (System(
            name=s.get('name', None), 
            x=s.get('X', None), 
            y=s.get('Y', None), 
            region=s.get('Region', None), 
            type='Rebel System', 
            importance=s.get('importance', None),
            rebel_affinity=s.get('rebel_affinity', None)))
        result.append(new_system)
    return result

@st.cache_data
def possible_rebel_system_names(minimum_rebel_affinity: float= 0.5):
    systems = possible_rebel_systems(minimum_rebel_affinity)
    names = [s.name for s in systems]
    return names
    
def affinity_as_float(affinity:str)-> float:
    if affinity == "Imperial":
        return 0.0
    elif affinity == "Imperial Sympathetic":
        return 0.25
    elif affinity == "Neutral":
        return 0.5
    elif affinity == "Rebel Sympathetic":
        return 0.75
    else:
        return 1.0


LANGUAGE_KEY = "Language"
COUNT_KEY = "Developers who know"

def get_current_top_skills(max: int = 10):
    query = f"""
MATCH (:Person)-[:KNOWS]->(t:Topic)
RETURN DISTINCT t.name as name, count(t.name) as count
ORDER BY count DESC LIMIT {max}
    """
    records = execute_query(query)
    result = []
    for r in records:
        result.append(
            {
                LANGUAGE_KEY: r.get('name'),
                COUNT_KEY: r.get('count')
            }
        )
    return result

@st.cache_data
def find_developers(
    team_size: int,
    req_skills: list[str],
    base: str,
    distance: int,
    reb_affinity: float
) -> list[str]:
    
    query = f"""
MATCH (p:Person)-[:KNOWS]->(t:Topic)
MATCH (p)-[f:FROM]->(s:System)-[d:CONNECTED_TO|NEAR*0..{distance}]->(s2:System)
MATCH (p)-[:KNOWS]->(c:Character)
WHERE ANY (name IN t.name WHERE name in $req_skills) AND s2.name = $base
WITH p, t, s, c, avg(c.rebel_affinity) as avg_affinity
WHERE avg_affinity >= {reb_affinity}
RETURN DISTINCT p.name as name, s.name as homeworld, collect(DISTINCT t.name) as skills, collect(DISTINCT c.name) as associates, avg(c.rebel_affinity) as avg_affinity LIMIT $team_size
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
            'homeworld': r.get('homeworld'),
            'skills': r.get('skills'),
            'associates': r.get('associates'),
            'affinity': r.get('avg_affinity')
        })
    return result

def devs_with_rank_info(
    base: str,
    cutoff_datetime: datetime
):
    if cutoff_datetime is None:
        # Set to 1/1/1970
        cutoff_datetime = datetime.datetime.utcfromtimestamp(0)
    query = f"""
MATCH (p:Person)-[r:KNOWS]->(t:Topic),
(p)-[:FROM]->(s:System),
(p)-[:KNOWS]->(c:Character),
(base:System),
path = shortestPath((s)-[:CONNECTED_TO|NEAR*0..100]-(base))
WHERE base.name = $base AND p.created_at >= datetime($datetime_cutoff)
WITH p, t, c, s, path
RETURN DISTINCT p.name as name, toString(p.created_at) as createdAt, p.email as email, s.name as homeworld, collect(DISTINCT c.name) as associates, collect(DISTINCT t.name) as devSkills, avg(c.rebel_affinity) as avg_associate_affinity, count(nodes(path)) as jumpsFromBase
    """
    params ={
        'base': base,
        'datetime_cutoff': cutoff_datetime.isoformat()
    }
    response = execute_query(query, params)
    result = []
    for r in response:
        created_at_string = r.get('createdAt', None)
        created_at = datetime.datetime.strptime(created_at_string, '%Y-%m-%dT%H:%M:%S.%fZ')
        # Below fails in streamlit cloud (using an older version of Python currently?)
        # created_at = datetime.datetime.fromisoformat(created_at_string) 
        dev = Person(
            name=r.get('name', None), 
            # email=r.get('email', None),
            homeworld=r.get('homeworld', None), 
            created_at=created_at,
            skills=r.get('devSkills', None), 
            associates=r.get('associates', None), 
            avg_associate_affinity=r.get('avg_associate_affinity', None),
            jumps_from_base=r.get('jumpsFromBase', None))
        result.append(dev)
    return result

def devs_ranked(
    devs: list[Person],
    skills: list[str],
    skills_points_per: float,
    associate_rebel_affinity: float,
    associate_rebel_affinity_points_per: float,
    max_distance_points: float,
    distance_decay_per_jump: float
):
    for dev in devs:
        dev_score = 0.0
        skill_points = 0.0
        affinity_points = 0.0
        distance_points = 0.0
        dev.matching_skills = 0
        for skill in skills:
            if skill in dev.skills:
                skill_points += skills_points_per
                dev.matching_skills += 1
        if dev.avg_associate_affinity is None or dev.avg_associate_affinity < associate_rebel_affinity:
            affinity_points = 0
        else:
            affinity_points = associate_rebel_affinity_points_per * dev.avg_associate_affinity
        distance_points =  max_distance_points - distance_decay_per_jump * dev.jumps_from_base
        if distance_points < 0:
            distance_points = 0

        dev_score += skill_points
        dev_score += affinity_points
        dev_score += distance_points
        dev.ranking_score = dev_score

    # Return list of devs ranked
    return sorted(devs, key=lambda x: x.ranking_score, reverse=True)

# UI

# HEADER BLOCK
# Convulted way to center image
col1, col2, col3 = st.columns([1,1,1])
with col1:
    st.write('')
    # Enable time based filtering
    enable_time_filter = st.checkbox('Filter by registration datetime')
    date_cutoff = None
    if enable_time_filter:
        now = datetime.datetime.now()
        date_cutoff = st.date_input('Date cutoff', now)
        time_cutoff = st.time_input('Time from', now - datetime.timedelta(minutes=DEFAULT_TIME_CUTOFF))
        date_cutoff = datetime.datetime.combine(date_cutoff, time_cutoff)
with col2:
    st.image('./media/hack_it.png')
with col3:
    st.write('')
    # Base location
    base1, base2 = st.columns(2)
    with base1:
        rebel_bases = possible_rebel_system_names()
        if st.button("Change Base Location"):
            rebel_base = random.choice(rebel_bases)
    with base2:
        if len(rebel_bases) == 0:
            st.write("No rebel bases found")
        else:
            rebel_base = random.choice(rebel_bases)
            st.write(f"Current Location: {rebel_base}")
    
    # Top skills
    st.write('Top skills in network:')
    top_skills = get_current_top_skills(st.secrets["TOP_SKILLS_TO_SHOW"])
    st.table(top_skills)

# st.title("Rebel Developers Network")
# st.markdown("<h1 style='text-align: center; color: white;'>Rebel Developers Network</h1>", unsafe_allow_html=True)

t1, t2, t3 = st.tabs(["Manual Search", "Ranking", "Data Analysis"])
with t1:
    with st.expander("Advanced Options"):
        team_size = st.slider("Team Size", 1, 12, 6)
        req_skills = st.multiselect("Team programming skills", programming_languages_list(), help="Select the programming languages needed for the team. Can be spread among team members.")

        t2c1, t2c2 = st.columns([1,1])
        with t2c1:
            base = st.selectbox("Location of Rebel Development Base", star_wars_systems())
        with t2c2:
            distance = st.slider("Max Hyperspace Jumps from Base", 1, 100, 10)

        reb_affinity = st.select_slider("Political Affinity", ["Imperial", "Imperial Sympathetic", "Neutral", "Rebel Sympathetic", "Rebel"], value = "Neutral")
    
    # TODO:
    if st.button("Find Rebel Developers"):
        developers = find_developers(
            team_size, 
            req_skills, 
            base, 
            distance, 
            affinity_as_float(reb_affinity))
        # Display suggested rebel developers
        st.json(developers)

with t2:
    with st.expander("Ranking Rubric"):

        rules1, rules2, rules3 = st.columns([1,1,1])
        with rules1:
            st.write("Skills")
            # Default skills
            top_3_skills = [t.get(LANGUAGE_KEY, None) for t in top_skills[:3]]

            # Desired Skills
            req_skills = st.multiselect(label="Team programming skills", options=programming_languages_list(), default = top_3_skills, help="Select the programming languages needed for the team. Can be spread among team members.", key="ranking_req_skills")
            # Skills Scoring
            skills_score = st.slider("Points per matching skill", 0, 100, 10)
        with rules2:
            st.write("Distance")
            # Distance Scoring
            distance_score = st.slider("Max Distance Score", 1, 100, 10)
            distance_score_dropoff = st.slider("Distance Score Dropoff/jump", 0.0, 10.0, 1.0)
        with rules3:
            st.write("Trustability")
            # Trustability Scoring
            trust_score = st.slider("Points per average associate affinity", 0, 100, 10, help="Points per average affinity of associates. Associates are people who know the developer and are also rebel sympathizers. This many points will be assigned for matching the requirement level + this number of points for each .1 above the requirement level.")
    
    devs = devs_with_rank_info(
        rebel_base,
        date_cutoff
        )
    devs_ranked = devs_ranked(
        devs=devs,
        skills=req_skills,
        skills_points_per=skills_score,
        associate_rebel_affinity=affinity_as_float(reb_affinity),
        associate_rebel_affinity_points_per=trust_score,
        max_distance_points=distance_score,
        distance_decay_per_jump=distance_score_dropoff
    )
    st.write("Developers Ranked")
    st.table(devs_ranked)        
            

with t3:
    # Building mode
    components.iframe("https://neodash.graphapp.io/", height=1000, scrolling=False)

    # TODO:
    # View only mode




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
