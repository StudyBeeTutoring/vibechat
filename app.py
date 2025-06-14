import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import random

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Food GO",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- POKEMON-THEMED ELEMENTS ---
FOOD_TYPES = {
    "Fruit": {"emoji": "🍎", "color": "#78C850", "xp": 20}, # Grass
    "Vegetable": {"emoji": "🥦", "color": "#A040A0", "xp": 25}, # Poison
    "Protein": {"emoji": "🍗", "color": "#C03028", "xp": 15}, # Fighting
    "Grains": {"emoji": "🍞", "color": "#E0C068", "xp": 15}, # Ground
    "Dairy": {"emoji": "🥛", "color": "#A8A878", "xp": 10}, # Normal
    "Treats/Snacks": {"emoji": "🍩", "color": "#705848", "xp": 5}, # Dark
    "Hydration": {"emoji": "💧", "color": "#6890F0", "xp": 10} # Water
}

HEALTHY_RECIPES = [
    "Grilled Chicken Salad with Avocado", "Quinoa Bowl with Roasted Vegetables",
    "Lentil Soup", "Berry and Spinach Smoothie", "Oatmeal with Nuts and Seeds",
    "Salmon with Asparagus", "Greek Yogurt with Honey and Berries"
]

# --- HELPER FUNCTIONS ---
def initialize_state():
    """Initializes all the session state variables."""
    if 'trainer_level' not in st.session_state:
        st.session_state.trainer_level = 1
    if 'trainer_xp' not in st.session_state:
        st.session_state.trainer_xp = 0
    if 'xp_to_next_level' not in st.session_state:
        st.session_state.xp_to_next_level = 100
    if 'logged_foods' not in st.session_state:
        st.session_state.logged_foods = []
    if 'food_dex' not in st.session_state:
        st.session_state.food_dex = set()
    if 'egg_progress' not in st.session_state:
        st.session_state.egg_progress = 0
    if 'egg_goal' not in st.session_state:
        st.session_state.egg_goal = 20 # Represents 20 minutes of activity

def level_up_check():
    """Checks for and handles trainer level ups."""
    if st.session_state.trainer_xp >= st.session_state.xp_to_next_level:
        st.session_state.trainer_level += 1
        st.session_state.trainer_xp -= st.session_state.xp_to_next_level
        st.session_state.xp_to_next_level = int(st.session_state.xp_to_next_level * 1.5)
        st.balloons()
        st.success(f"🎉 Congratulations! You reached Trainer Level {st.session_state.trainer_level}! 🎉")

# --- INITIALIZE STATE ---
initialize_state()


# --- SIDEBAR - TRAINER PROFILE ---
with st.sidebar:
    st.title("👨‍🍳 Trainer Profile")
    st.header(f"Level: {st.session_state.trainer_level}")
    
    # XP Bar
    st.progress(st.session_state.trainer_xp / st.session_state.xp_to_next_level)
    st.markdown(f"**XP:** {st.session_state.trainer_xp} / {st.session_state.xp_to_next_level}")
    
    st.divider()
    
    # Food-Dex Stats
    st.header("🍎 Food-Dex")
    st.metric(label="Unique Foods Logged", value=f"{len(st.session_state.food_dex)}")
    
    st.divider()
    
    # App Info
    st.info("Log food to gain XP, level up, and complete your Food-Dex!")


# --- MAIN APP ---
st.title("Food GO: Your Gamified Nutrition Tracker")
st.markdown("Log your meals to 'catch' them, gain experience, and build a healthy lifestyle!")

# --- CATCH ZONE (Food Logging) ---
st.header("👇 Catch a new Food!")

with st.form("catch_food_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        food_name = st.text_input("Food Name", placeholder="e.g., Apple, Chicken Breast")
    with col2:
        calories = st.number_input("Calories (kcal)", min_value=0, step=10)
    with col3:
        food_type = st.selectbox("Food Type", options=list(FOOD_TYPES.keys()))

    submitted = st.form_submit_button("✅ Log Food!")

    if submitted:
        if not food_name:
            st.warning("Please enter a food name.")
        else:
            xp_gained = FOOD_TYPES[food_type]['xp']
            
            # Add to log
            st.session_state.logged_foods.append({
                "Timestamp": datetime.now(),
                "Name": food_name.title(),
                "Type": food_type,
                "Calories": calories,
                "XP": xp_gained
            })
            
            # Add to Food-Dex (if new)
            is_new_dex_entry = food_name.title() not in st.session_state.food_dex
            if is_new_dex_entry:
                st.session_state.food_dex.add(food_name.title())
                xp_gained += 50 # Bonus XP for new discovery!
            
            # Update XP and check for level up
            st.session_state.trainer_xp += xp_gained
            level_up_check()
            
            # Success message
            type_emoji = FOOD_TYPES[food_type]['emoji']
            dex_message = "It's a new Food-Dex entry! +50 bonus XP!" if is_new_dex_entry else ""
            st.success(f"Gotcha! {food_name.title()} ({type_emoji}) was caught! You gained {xp_gained} XP. {dex_message}")

st.divider()

# --- DAILY DASHBOARD ---
st.header(f"🗓️ Today's Dashboard ({datetime.now().strftime('%Y-%m-%d')})")

today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
todays_log = [f for f in st.session_state.logged_foods if f['Timestamp'] >= today_start]

if not todays_log:
    st.info("You haven't logged any food yet today. Go catch some!")
else:
    df_today = pd.DataFrame(todays_log)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Calorie Summary
        total_calories = df_today['Calories'].sum()
        st.metric("Total Calories Today", f"{total_calories:,.0f} kcal")
        
        # Latest Logs
        st.subheader("Recent Catches:")
        st.dataframe(
            df_today[['Name', 'Type', 'Calories']].tail(5),
            use_container_width=True,
            hide_index=True
        )

    with col2:
        # Food Type Distribution
        st.subheader("Food Type Distribution")
        type_counts = df_today['Type'].value_counts()
        
        # Create a pie chart with Plotly
        fig = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            title="Today's Meal Composition",
            color=type_counts.index,
            color_discrete_map={k: v['color'] for k, v in FOOD_TYPES.items()}
        )
        fig.update_layout(showlegend=False)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- FOOD-DEX & ACTIVITY ---
tab1, tab2 = st.tabs(["🍎 My Food-Dex", "🥚 Hatch a Nutri-Egg"])

with tab1:
    st.header("Your Personal Food-Dex")
    st.write("A record of every unique food you've ever 'caught'.")

    if not st.session_state.food_dex:
        st.warning("Your Food-Dex is empty. Log some food to start filling it!")
    else:
        dex_list = sorted(list(st.session_state.food_dex))
        
        # Display in a grid
        num_columns = 4
        cols = st.columns(num_columns)
        for i, food_item in enumerate(dex_list):
            with cols[i % num_columns]:
                st.info(f"#{i+1:03d}\n**{food_item}**")
                
with tab2:
    st.header("Hatch a Nutri-Egg by Being Active!")
    st.write(f"Log **{st.session_state.egg_goal} minutes** of physical activity to hatch your egg and discover a healthy recipe!")

    # Egg progress bar
    st.progress(st.session_state.egg_progress / st.session_state.egg_goal, text=f"Progress: {st.session_state.egg_progress}/{st.session_state.egg_goal} mins")

    with st.form("activity_form", clear_on_submit=True):
        activity_minutes = st.number_input("Log Activity (in minutes)", min_value=1, step=5)
        log_activity_btn = st.form_submit_button("🏃‍♂️ Log Activity")

        if log_activity_btn:
            st.session_state.egg_progress += activity_minutes
            st.success(f"Great job! You logged {activity_minutes} minutes of activity.")

            # Check for hatch
            if st.session_state.egg_progress >= st.session_state.egg_goal:
                hatched_recipe = random.choice(HEALTHY_RECIPES)
                st.balloons()
                st.success("Oh? Your Nutri-Egg is hatching!")
                st.subheader("✨ You discovered a new recipe! ✨")
                st.success(f"**{hatched_recipe}**")
                
                # Reset for a new egg
                st.session_state.egg_progress = 0
                st.info("A new Nutri-Egg has appeared! Keep up the great work.")
            
