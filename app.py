import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import random
from sqlalchemy import text # <- ADD THIS IMPORT

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Food GO",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATABASE SETUP ---
conn = st.connection("food_db", type="sql", url="sqlite:///food_go.db")

def init_db():
    """Initialize the database tables if they don't exist."""
    with conn.session as s:
        # <- WRAP ALL s.execute() calls with text()
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY,
                trainer_level INTEGER DEFAULT 1,
                trainer_xp INTEGER DEFAULT 0,
                xp_to_next_level INTEGER DEFAULT 100,
                bmi REAL DEFAULT 0,
                target_weight REAL DEFAULT 0,
                target_calories INTEGER DEFAULT 2000,
                egg_progress INTEGER DEFAULT 0,
                buddy_name TEXT DEFAULT 'Fruity',
                onboarded BOOLEAN DEFAULT FALSE
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS food_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                name TEXT,
                type TEXT,
                calories INTEGER,
                xp INTEGER
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS food_dex (
                name TEXT PRIMARY KEY
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS badges (
                name TEXT PRIMARY KEY,
                emoji TEXT,
                description TEXT,
                earned_on DATE
            );
        """))
        # Check for user profile
        user_profile = s.execute(text("SELECT * FROM user_profile WHERE id = 1;")).fetchone()
        if not user_profile:
            s.execute(text("INSERT INTO user_profile (id) VALUES (1);"))
        s.commit()

# --- GAME & UI ELEMENTS (No changes here) ---
FOOD_TYPES = {
    "Fruit": {"emoji": "🍎", "color": "#78C850", "xp": 20},
    "Vegetable": {"emoji": "🥦", "color": "#A040A0", "xp": 25},
    "Protein": {"emoji": "🍗", "color": "#C03028", "xp": 15},
    "Grains": {"emoji": "🍞", "color": "#E0C068", "xp": 15},
    "Dairy": {"emoji": "🥛", "color": "#A8A878", "xp": 10},
    "Treats/Snacks": {"emoji": "🍩", "color": "#705848", "xp": 5},
    "Hydration": {"emoji": "💧", "color": "#6890F0", "xp": 10}
}
BUDDIES = {
    "Fruity 🍎": "A cheerful apple that loves healthy starts!",
    "Brocco 💪": "A strong broccoli that champions green veggies!",
    "Chicky 🍗": "A reliable chicken drumstick, great for protein goals!"
}
BADGES = {
    "Boulder Badge": {"emoji": "🪨", "desc": "Log 5 unique 'Grains' food.", "check": lambda: conn.query("SELECT COUNT(DISTINCT name) FROM food_log WHERE type = 'Grains';")['count(distinct name)'][0] >= 5},
    "Cascade Badge": {"emoji": "💧", "desc": "Log 'Hydration' for 7 days.", "check": lambda: conn.query("SELECT COUNT(DISTINCT date(timestamp)) FROM food_log WHERE type = 'Hydration';")['count(distinct date(timestamp))'][0] >= 7},
    "Rainbow Badge": {"emoji": "🌈", "desc": "Log a food from every type.", "check": lambda: conn.query("SELECT COUNT(DISTINCT type) FROM food_log;")['count(distinct type)'][0] >= len(FOOD_TYPES)},
    "Pioneer Badge": {"emoji": "🧭", "desc": "Log your first 10 unique foods.", "check": lambda: conn.query("SELECT COUNT(*) FROM food_dex;")['count(*)'][0] >= 10},
}
# (Recipes are at the end of the file)

# --- HELPER & DB FUNCTIONS ---
def load_user_state():
    """Load user profile from DB into session state."""
    # conn.query is fine, only s.execute needs text()
    user_data = conn.query("SELECT * FROM user_profile WHERE id = 1;", ttl=0).to_dict('records')[0]
    for key, value in user_data.items():
        st.session_state[key] = value

def save_user_state():
    """Save relevant session state back to the DB."""
    with conn.session as s:
        s.execute(text(f"""
            UPDATE user_profile SET 
                trainer_level = {st.session_state.trainer_level},
                trainer_xp = {st.session_state.trainer_xp},
                xp_to_next_level = {st.session_state.xp_to_next_level},
                egg_progress = {st.session_state.egg_progress}
            WHERE id = 1;
        """))
        s.commit()

def check_and_award_badges():
    """Check if any new badges have been earned."""
    earned_badges = conn.query("SELECT name FROM badges;", ttl=0)['name'].tolist()
    for name, data in BADGES.items():
        if name not in earned_badges:
            if data["check"]():
                with conn.session as s:
                    s.execute(text(f"""
                        INSERT INTO badges (name, emoji, description, earned_on) 
                        VALUES ('{name}', '{data['emoji']}', '{data['desc']}', '{datetime.now().date()}');
                    """))
                    s.commit()
                st.balloons()
                st.success(f"🏆 You've earned the {data['emoji']} {name}! Check your Trainer Card!")

# --- INITIALIZE APP ---
init_db()
if 'onboarded' not in st.session_state:
    load_user_state()

# --- ONBOARDING PROCESS ---
if not st.session_state.onboarded:
    st.title("Welcome to Food GO! 🥗")
    st.header("Let's create your Trainer Card.")
    with st.form("onboarding_form"):
        buddy_name = st.selectbox("First, choose your Food Buddy!", options=BUDDIES.keys(), help="Your buddy will cheer you on!")
        unit_system = st.radio("Unit System", ("Metric (cm/kg)", "Imperial (ft/in/lbs)"))
        col1, col2 = st.columns(2)
        if unit_system == "Metric (cm/kg)":
            with col1: height_cm = st.number_input("Height (cm)", 100, 250, 170)
            with col2: weight_kg = st.number_input("Weight (kg)", 30.0, 200.0, 70.0, 0.1)
        else:
            with col1:
                height_ft = st.number_input("Height (ft)", 3, 8, 5)
                height_in = st.number_input("Height (in)", 0, 11, 9)
            with col2: weight_lbs = st.number_input("Weight (lbs)", 60.0, 450.0, 155.0, 0.1)
        
        goal = st.selectbox("What is your primary goal?", ("Lose Weight", "Maintain Weight", "Gain Weight"))
        submitted = st.form_submit_button("Start My Adventure!")

        if submitted:
            if unit_system == "Imperial (ft/in/lbs)":
                height_m = (height_ft * 12 + height_in) * 0.0254
                weight_kg_val = weight_lbs * 0.453592
            else:
                height_m = height_cm / 100
                weight_kg_val = weight_kg
            bmi = round(weight_kg_val / (height_m ** 2), 1)
            target_weight = round(22 * (height_m ** 2), 1)
            target_calories = 1700 if goal == "Lose Weight" else 2300 if goal == "Gain Weight" else 2000
            
            with conn.session as s:
                s.execute(text(f"""
                    UPDATE user_profile SET
                        bmi = {bmi}, target_weight = {target_weight}, target_calories = {target_calories},
                        buddy_name = '{buddy_name}', onboarded = TRUE
                    WHERE id = 1;
                """))
                s.commit()
            st.success("Your Trainer Card is ready! Let the journey begin!")
            st.rerun()

# --- MAIN APP (runs only after onboarding) ---
else:
    # Sidebar, Main content, Tabs... the rest of the code is unchanged.
    # The important changes were only in the database functions.
    # --- SIDEBAR - TRAINER CARD ---
    with st.sidebar:
        st.title("Trainer Card 💳")
        st.header(f"Level: {st.session_state.trainer_level}")
        st.progress(st.session_state.trainer_xp / st.session_state.xp_to_next_level)
        st.markdown(f"**XP:** {st.session_state.trainer_xp} / {st.session_state.xp_to_next_level}")
        
        st.divider()
        st.subheader("Your Buddy")
        buddy_emoji = st.session_state.buddy_name.split(" ")[-1]
        st.markdown(f"### {st.session_state.buddy_name}")
        st.write(f"_{BUDDIES[st.session_state.buddy_name]}_")

        st.divider()
        st.subheader("Health Stats")
        st.metric(label="Your BMI", value=f"{st.session_state.bmi}")
        st.metric(label="Target Weight", value=f"{st.session_state.target_weight} kg")

        st.divider()
        st.subheader("Achievement Badges")
        earned_badges_df = conn.query("SELECT * FROM badges;", ttl=60)
        if earned_badges_df.empty:
            st.caption("No badges yet. Keep logging to earn them!")
        else:
            for _, badge in earned_badges_df.iterrows():
                st.markdown(f"{badge['emoji']} **{badge['name']}**")
    
    # --- MAIN APP CONTENT ---
    st.title(f"Food GO {random.choice(['🌿','🔥','💧'])}")
    st.markdown("A wild food appeared! What will you do?")

    # --- CATCH ZONE ---
    with st.form("catch_food_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        food_name = col1.text_input("Food Name", placeholder="e.g., Apple")
        calories = col2.number_input("Calories (kcal)", 0, step=10)
        food_type = col3.selectbox("Food Type", options=list(FOOD_TYPES.keys()))
        submitted = st.form_submit_button(f"Throw a Poké Ball! 🔴")

        if submitted and food_name:
            xp_gained = FOOD_TYPES[food_type]['xp']
            timestamp = datetime.now()
            
            with conn.session as s:
                s.execute(text(f"""
                    INSERT INTO food_log (timestamp, name, type, calories, xp)
                    VALUES ('{timestamp}', '{food_name.title()}', '{food_type}', {calories}, {xp_gained});
                """))
                s.commit()
            
            dex_list = conn.query("SELECT name FROM food_dex;", ttl=0)['name'].tolist()
            is_new_dex_entry = food_name.title() not in dex_list
            if is_new_dex_entry:
                with conn.session as s:
                    s.execute(text(f"INSERT INTO food_dex (name) VALUES ('{food_name.title()}');"))
                    s.commit()
                xp_gained += 50
            
            st.session_state.trainer_xp += xp_gained
            if st.session_state.trainer_xp >= st.session_state.xp_to_next_level:
                st.session_state.trainer_level += 1
                st.session_state.trainer_xp -= st.session_state.xp_to_next_level
                st.session_state.xp_to_next_level = int(st.session_state.xp_to_next_level * 1.5)
                st.balloons()
                st.success(f"🎉 Congratulations! You reached Trainer Level {st.session_state.trainer_level}! 🎉")

            save_user_state()
            check_and_award_badges()

            type_emoji = FOOD_TYPES[food_type]['emoji']
            dex_message = "New Food-Dex entry! +50 bonus XP!" if is_new_dex_entry else ""
            st.success(f"Gotcha! {food_name.title()} ({type_emoji}) was caught! +{xp_gained} XP. {dex_message}")
            st.rerun()

    st.divider()

    # --- DASHBOARD & ANALYSIS TABS ---
    tab1, tab2, tab3 = st.tabs(["🗓️ Daily Journal", "📈 Progress Chart", "🥚 Nutri-Egg"])

    with tab1:
        st.header("Daily Journal")
        selected_date = st.date_input("View log for date:", datetime.now())
        
        log_df = conn.query(f"SELECT * FROM food_log WHERE date(timestamp) = '{selected_date}';", ttl=0)

        if log_df.empty:
            st.info(f"Nothing logged on {selected_date}. Go catch some food!")
        else:
            total_calories = log_df['calories'].sum()
            calorie_diff = total_calories - st.session_state.target_calories
            col1, col2 = st.columns([1, 1])
            with col1:
                st.metric(
                    label="Daily Calorie Goal",
                    value=f"{total_calories:,.0f} / {st.session_state.target_calories} kcal",
                    delta=f"{calorie_diff:,.0f} kcal from target",
                    delta_color="inverse"
                )
                st.dataframe(log_df[['name', 'type', 'calories']].rename(columns=str.title), use_container_width=True)
            with col2:
                st.subheader("Meal Composition")
                type_counts = log_df['type'].value_counts()
                fig = px.pie(values=type_counts.values, names=type_counts.index, color=type_counts.index,
                             color_discrete_map={k: v['color'] for k, v in FOOD_TYPES.items()})
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("Your Progress Over Time")
        days_to_show = st.slider("Number of past days to display:", 7, 30, 7)
        start_date = datetime.now().date() - timedelta(days=days_to_show - 1)
        
        history_df = conn.query(f"""
            SELECT date(timestamp) as log_date, SUM(calories) as total_calories
            FROM food_log
            WHERE date(timestamp) >= '{start_date}'
            GROUP BY log_date
            ORDER BY log_date;
        """, ttl=60)

        if history_df.empty:
            st.warning("Not enough data to show a trend. Keep logging!")
        else:
            fig = px.line(history_df, x='log_date', y='total_calories', markers=True,
                          title=f"Calorie Intake for Last {days_to_show} Days",
                          labels={'log_date': 'Date', 'total_calories': 'Total Calories (kcal)'})
            fig.add_hline(y=st.session_state.target_calories, line_dash="dot",
                          annotation_text="Your Target", annotation_position="bottom right")
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("Hatch a Nutri-Egg!")
        st.write(f"Log **30 minutes** of physical activity to hatch your egg and discover a healthy recipe!")
        st.progress(st.session_state.egg_progress / 30, text=f"Progress: {st.session_state.egg_progress}/30 mins")

        if st.session_state.egg_progress >= 30:
            hatched_recipe = random.choice(HEALTHY_RECIPES)
            st.balloons()
            st.success("Oh? Your Nutri-Egg is hatching!")
            with st.expander(f"✨ You discovered: {hatched_recipe['name']} ✨", expanded=True):
                st.markdown("**Ingredients:**\n" + "\n".join([f"- {item}" for item in hatched_recipe['ingredients']]))
                st.markdown("\n**Instructions:**\n" + hatched_recipe['instructions'])
            st.session_state.egg_progress = 0
            save_user_state()
            if st.button("Start a new Egg! ✨"):
                st.rerun()
        else:
            with st.form("activity_form"):
                activity_minutes = st.number_input("Log Activity (in minutes)", 1, 60, 10)
                if st.form_submit_button("🏃‍♂️ Log Activity"):
                    st.session_state.egg_progress += activity_minutes
                    save_user_state()
                    st.success(f"Great job! You logged {activity_minutes} minutes.")
                    st.rerun()

# --- RECIPES LIST ---
HEALTHY_RECIPES = [
    {"name": "Quinoa Bowl with Roasted Veggies & Chickpeas", "ingredients": ["1 cup quinoa", "1 head of broccoli, chopped", "1 red bell pepper, sliced", "1 can (15 oz) chickpeas, rinsed", "2 tbsp olive oil", "1 tsp paprika", "Salt and pepper", "Lemon-tahini dressing"], "instructions": "1. Preheat oven to 400°F (200°C). Toss broccoli, bell pepper, and chickpeas with olive oil, paprika, salt, and pepper. Roast for 20-25 minutes. \n2. Cook quinoa according to package directions. \n3. Assemble bowls with a base of quinoa, topped with roasted veggies and chickpeas. Drizzle with lemon-tahini dressing."},
    {"name": "Grilled Salmon with Asparagus and Lemon", "ingredients": ["2 salmon fillets (6 oz each)", "1 bunch asparagus, trimmed", "1 tbsp olive oil", "1 lemon, sliced", "2 cloves garlic, minced", "Salt and pepper"], "instructions": "1. Preheat grill or grill pan to medium-high. \n2. Toss asparagus with olive oil, minced garlic, salt, and pepper. \n3. Season salmon fillets with salt and pepper. \n4. Grill salmon for 4-6 minutes per side, until cooked through. Grill asparagus for 5-7 minutes, until tender-crisp. \n5. Serve salmon and asparagus with fresh lemon slices."},
    {"name": "Hearty Lentil Soup", "ingredients": ["1 tbsp olive oil", "1 onion, chopped", "2 carrots, diced", "2 celery stalks, diced", "2 cloves garlic, minced", "1 cup brown or green lentils, rinsed", "8 cups vegetable broth", "1 tsp dried thyme", "1 bay leaf", "Salt and pepper"], "instructions": "1. In a large pot, heat olive oil over medium heat. Add onion, carrots, and celery and cook until softened (about 5-7 minutes). Add garlic and cook for another minute. \n2. Stir in lentils, vegetable broth, thyme, and bay leaf. \n3. Bring to a boil, then reduce heat and simmer for 45-60 minutes, until lentils are tender. Remove bay leaf and season with salt and pepper before serving."},
    {"name": "Avocado Toast with Egg", "ingredients": ["2 slices whole-wheat bread, toasted", "1 ripe avocado", "2 eggs", "1/4 tsp red pepper flakes (optional)", "Salt and pepper"], "instructions": "1. Mash the avocado in a small bowl and season with salt and pepper. \n2. Cook eggs to your liking (fried, poached, or scrambled). \n3. Spread the mashed avocado evenly on the toasted bread. \n4. Top each slice with an egg and a sprinkle of red pepper flakes, if using."},
    {"name": "Berry and Spinach Power Smoothie", "ingredients": ["1 cup spinach", "1/2 cup mixed berries (frozen)", "1/2 banana", "1/2 cup Greek yogurt or almond milk", "1 tbsp chia seeds"], "instructions": "1. Combine all ingredients in a blender. \n2. Blend until smooth. Add a little more liquid if it's too thick. \n3. Pour into a glass and enjoy immediately."},
    {"name": "Chicken and Black Bean Burrito Bowl", "ingredients": ["1 cooked chicken breast, shredded", "1/2 cup cooked brown rice", "1/2 cup canned black beans, rinsed", "1/4 cup corn", "Salsa, to taste", "Shredded lettuce", "Lime wedge"], "instructions": "1. Assemble your bowl by starting with a base of brown rice. \n2. Top with shredded chicken, black beans, corn, and shredded lettuce. \n3. Add a generous spoonful of salsa and a squeeze of fresh lime juice."}
]
