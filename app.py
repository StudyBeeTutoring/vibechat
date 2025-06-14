import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import random

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Food GO",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- POKEMON-THEMED ELEMENTS & RECIPES ---
FOOD_TYPES = {
    "Fruit": {"emoji": "🍎", "color": "#78C850", "xp": 20}, # Grass
    "Vegetable": {"emoji": "🥦", "color": "#A040A0", "xp": 25}, # Poison
    "Protein": {"emoji": "🍗", "color": "#C03028", "xp": 15}, # Fighting
    "Grains": {"emoji": "🍞", "color": "#E0C068", "xp": 15}, # Ground
    "Dairy": {"emoji": "🥛", "color": "#A8A878", "xp": 10}, # Normal
    "Treats/Snacks": {"emoji": "🍩", "color": "#705848", "xp": 5}, # Dark
    "Hydration": {"emoji": "💧", "color": "#6890F0", "xp": 10} # Water
}

# --- EXPANDED & DETAILED RECIPES ---
HEALTHY_RECIPES = [
    {
        "name": "Quinoa Bowl with Roasted Veggies & Chickpeas",
        "ingredients": ["1 cup quinoa", "1 head of broccoli, chopped", "1 red bell pepper, sliced", "1 can (15 oz) chickpeas, rinsed", "2 tbsp olive oil", "1 tsp paprika", "Salt and pepper to taste", "Lemon-tahini dressing"],
        "instructions": "1. Preheat oven to 400°F (200°C). Toss broccoli, bell pepper, and chickpeas with olive oil, paprika, salt, and pepper. Roast for 20-25 minutes. \n2. Cook quinoa according to package directions. \n3. Assemble bowls with a base of quinoa, topped with roasted veggies and chickpeas. Drizzle with lemon-tahini dressing."
    },
    {
        "name": "Grilled Salmon with Asparagus and Lemon",
        "ingredients": ["2 salmon fillets (6 oz each)", "1 bunch asparagus, trimmed", "1 tbsp olive oil", "1 lemon, sliced", "2 cloves garlic, minced", "Salt and pepper"],
        "instructions": "1. Preheat grill or grill pan to medium-high. \n2. Toss asparagus with olive oil, minced garlic, salt, and pepper. \n3. Season salmon fillets with salt and pepper. \n4. Grill salmon for 4-6 minutes per side, until cooked through. Grill asparagus for 5-7 minutes, until tender-crisp. \n5. Serve salmon and asparagus with fresh lemon slices."
    },
    {
        "name": "Hearty Lentil Soup",
        "ingredients": ["1 tbsp olive oil", "1 onion, chopped", "2 carrots, diced", "2 celery stalks, diced", "2 cloves garlic, minced", "1 cup brown or green lentils, rinsed", "8 cups vegetable broth", "1 tsp dried thyme", "1 bay leaf", "Salt and pepper"],
        "instructions": "1. In a large pot, heat olive oil over medium heat. Add onion, carrots, and celery and cook until softened (about 5-7 minutes). Add garlic and cook for another minute. \n2. Stir in lentils, vegetable broth, thyme, and bay leaf. \n3. Bring to a boil, then reduce heat and simmer for 45-60 minutes, until lentils are tender. Remove bay leaf and season with salt and pepper before serving."
    },
    {
        "name": "Avocado Toast with Egg",
        "ingredients": ["2 slices whole-wheat bread, toasted", "1 ripe avocado", "2 eggs", "1/4 tsp red pepper flakes (optional)", "Salt and pepper"],
        "instructions": "1. Mash the avocado in a small bowl and season with salt and pepper. \n2. Cook eggs to your liking (fried, poached, or scrambled). \n3. Spread the mashed avocado evenly on the toasted bread. \n4. Top each slice with an egg and a sprinkle of red pepper flakes, if using."
    },
    {
        "name": "Berry and Spinach Power Smoothie",
        "ingredients": ["1 cup spinach", "1/2 cup mixed berries (frozen)", "1/2 banana", "1/2 cup Greek yogurt or almond milk", "1 tbsp chia seeds"],
        "instructions": "1. Combine all ingredients in a blender. \n2. Blend until smooth. Add a little more liquid if it's too thick. \n3. Pour into a glass and enjoy immediately."
    },
    {
        "name": "Chicken and Black Bean Burrito Bowl",
        "ingredients": ["1 cooked chicken breast, shredded", "1/2 cup cooked brown rice", "1/2 cup canned black beans, rinsed", "1/4 cup corn", "Salsa, to taste", "Shredded lettuce", "Lime wedge"],
        "instructions": "1. Assemble your bowl by starting with a base of brown rice. \n2. Top with shredded chicken, black beans, corn, and shredded lettuce. \n3. Add a generous spoonful of salsa and a squeeze of fresh lime juice."
    }
]


# --- HELPER FUNCTIONS ---
def initialize_state():
    """Initializes all the session state variables."""
    # Onboarding and user stats
    if 'onboarded' not in st.session_state:
        st.session_state.onboarded = False
    if 'bmi' not in st.session_state:
        st.session_state.bmi = 0
    if 'target_weight' not in st.session_state:
        st.session_state.target_weight = 0
    if 'target_calories' not in st.session_state:
        st.session_state.target_calories = 2000

    # Gamification stats
    if 'trainer_level' not in st.session_state:
        st.session_state.trainer_level = 1
    if 'trainer_xp' not in st.session_state:
        st.session_state.trainer_xp = 0
    if 'xp_to_next_level' not in st.session_state:
        st.session_state.xp_to_next_level = 100

    # Data logs
    if 'logged_foods' not in st.session_state:
        st.session_state.logged_foods = []
    if 'food_dex' not in st.session_state:
        st.session_state.food_dex = set()
    
    # Activity
    if 'egg_progress' not in st.session_state:
        st.session_state.egg_progress = 0
    if 'egg_goal' not in st.session_state:
        st.session_state.egg_goal = 30 # Increased goal to 30 mins

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


# --- ONBOARDING PROCESS ---
if not st.session_state.onboarded:
    st.title("Welcome to Food GO! 🥗")
    st.header("Let's set up your profile.")
    st.write("To personalize your experience, we need a few details. This is a one-time setup.")

    with st.form("onboarding_form"):
        st.subheader("Your Metrics")
        unit_system = st.radio("Unit System", ("Metric (cm/kg)", "Imperial (ft/in/lbs)"))
        
        col1, col2 = st.columns(2)
        if unit_system == "Metric (cm/kg)":
            with col1:
                height_cm = st.number_input("Height (cm)", min_value=100, max_value=250, value=170)
            with col2:
                weight_kg = st.number_input("Weight (kg)", min_value=30.0, max_value=200.0, value=70.0, step=0.1)
        else: # Imperial
            with col1:
                height_ft = st.number_input("Height (ft)", min_value=3, max_value=8, value=5)
                height_in = st.number_input("Height (in)", min_value=0, max_value=11, value=9)
            with col2:
                weight_lbs = st.number_input("Weight (lbs)", min_value=60.0, max_value=450.0, value=155.0, step=0.1)

        st.subheader("Your Goal")
        goal = st.selectbox("What is your primary goal?", ("Lose Weight", "Maintain Weight", "Gain Weight"))
        
        submitted = st.form_submit_button("Create My Profile!")

        if submitted:
            # Convert to metric for universal calculations
            if unit_system == "Imperial (ft/in/lbs)":
                height_m = (height_ft * 12 + height_in) * 0.0254
                weight_kg = weight_lbs * 0.453592
            else:
                height_m = height_cm / 100

            # Calculations
            bmi = weight_kg / (height_m ** 2)
            # Target weight for a BMI of 22 (middle of healthy range)
            target_weight = 22 * (height_m ** 2)
            
            # Simple calorie target calculation (adjust base of 2000)
            if goal == "Lose Weight":
                target_calories = 1700
            elif goal == "Maintain Weight":
                target_calories = 2000
            else: # Gain Weight
                target_calories = 2300

            # Store in session state
            st.session_state.bmi = round(bmi, 1)
            st.session_state.target_weight = round(target_weight, 1)
            st.session_state.target_calories = target_calories
            st.session_state.onboarded = True
            
            st.success("Your profile is set up! The app will now load.")
            st.rerun() # Rerun the script to show the main app

# --- MAIN APP (runs only after onboarding) ---
else:
    # --- SIDEBAR - TRAINER PROFILE ---
    with st.sidebar:
        st.title("👨‍🍳 Trainer Profile")
        st.header(f"Level: {st.session_state.trainer_level}")
        
        st.progress(st.session_state.trainer_xp / st.session_state.xp_to_next_level)
        st.markdown(f"**XP:** {st.session_state.trainer_xp} / {st.session_state.xp_to_next_level}")
        
        st.divider()

        st.header("Your Health Stats")
        st.metric(label="Your BMI", value=f"{st.session_state.bmi}")
        st.metric(label="Suggested Target Weight", value=f"{st.session_state.target_weight} kg")
        st.info("💡 This is a guideline based on a healthy BMI range, not medical advice.")

        st.divider()
        st.header("🍎 Food-Dex")
        st.metric(label="Unique Foods Logged", value=f"{len(st.session_state.food_dex)}")

    # --- MAIN APP CONTENT ---
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

        if submitted and food_name:
            xp_gained = FOOD_TYPES[food_type]['xp']
            st.session_state.logged_foods.append({
                "Timestamp": datetime.now(), "Name": food_name.title(),
                "Type": food_type, "Calories": calories, "XP": xp_gained
            })
            
            is_new_dex_entry = food_name.title() not in st.session_state.food_dex
            if is_new_dex_entry:
                st.session_state.food_dex.add(food_name.title())
                xp_gained += 50
            
            st.session_state.trainer_xp += xp_gained
            level_up_check()
            
            type_emoji = FOOD_TYPES[food_type]['emoji']
            dex_message = "It's a new Food-Dex entry! +50 bonus XP!" if is_new_dex_entry else ""
            st.success(f"Gotcha! {food_name.title()} ({type_emoji}) was caught! You gained {xp_gained} XP. {dex_message}")
        elif submitted and not food_name:
            st.warning("Please enter a food name.")

    st.divider()

    # --- DAILY DASHBOARD ---
    st.header(f"🗓️ Today's Dashboard ({datetime.now().strftime('%Y-%m-%d')})")
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    todays_log = [f for f in st.session_state.logged_foods if f['Timestamp'] >= today_start]

    if not todays_log:
        st.info("You haven't logged any food yet today. Go catch some!")
    else:
        df_today = pd.DataFrame(todays_log)
        total_calories = df_today['Calories'].sum()
        calorie_diff = total_calories - st.session_state.target_calories
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.metric(
                label="Daily Calorie Goal",
                value=f"{total_calories:,.0f} / {st.session_state.target_calories} kcal",
                delta=f"{calorie_diff:,.0f} kcal from target",
                delta_color="inverse"
            )
            st.subheader("Recent Catches:")
            st.dataframe(
                df_today[['Name', 'Type', 'Calories']].tail(5),
                use_container_width=True, hide_index=True
            )
        with col2:
            st.subheader("Food Type Distribution")
            type_counts = df_today['Type'].value_counts()
            fig = px.pie(
                values=type_counts.values, names=type_counts.index, title="Today's Meal Composition",
                color=type_counts.index, color_discrete_map={k: v['color'] for k, v in FOOD_TYPES.items()}
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
            num_columns = 4
            cols = st.columns(num_columns)
            for i, food_item in enumerate(dex_list):
                with cols[i % num_columns]:
                    st.info(f"#{i+1:03d}\n**{food_item}**")
                    
    with tab2:
        st.header("Hatch a Nutri-Egg by Being Active!")
        st.write(f"Log **{st.session_state.egg_goal} minutes** of physical activity to hatch your egg and discover a healthy recipe!")
        st.progress(st.session_state.egg_progress / st.session_state.egg_goal, text=f"Progress: {st.session_state.egg_progress}/{st.session_state.egg_goal} mins")

        with st.form("activity_form", clear_on_submit=True):
            activity_minutes = st.number_input("Log Activity (in minutes)", min_value=1, step=5)
            log_activity_btn = st.form_submit_button("🏃‍♂️ Log Activity")
            if log_activity_btn:
                st.session_state.egg_progress += activity_minutes
                st.success(f"Great job! You logged {activity_minutes} minutes of activity.")

                if st.session_state.egg_progress >= st.session_state.egg_goal:
                    hatched_recipe = random.choice(HEALTHY_RECIPES)
                    st.balloons()
                    st.success("Oh? Your Nutri-Egg is hatching!")
                    
                    st.subheader(f"✨ You discovered: {hatched_recipe['name']} ✨")
                    
                    st.markdown("**Ingredients:**")
                    ingredients_md = ""
                    for item in hatched_recipe['ingredients']:
                        ingredients_md += f"- {item}\n"
                    st.markdown(ingredients_md)
                    
                    st.markdown("**Instructions:**")
                    st.write(hatched_recipe['instructions'])
                    
                    st.session_state.egg_progress = 0
                    st.info("A new Nutri-Egg has appeared! Keep up the great work.")
                
                # We need to rerun to update the progress bar visual immediately after form submission
                st.rerun()
