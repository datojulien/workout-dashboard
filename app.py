import pandas as pd
import streamlit as st

# Set up the Streamlit page
st.set_page_config(page_title="🏋️ Workout Dashboard", layout="wide")

st.title("🏋️ Workout Dashboard")
st.markdown("Track your workouts by day or by exercise. Personal bests are marked with 🏅.")

# Load CSV from GitHub
csv_url = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# ❌ Skip cardio entries like Stair Stepper
df = df[~df['Exercise'].str.contains("Stair Stepper", case=False, na=False)]

# ✅ Calculate actual weight (with multiplier) and total volume
df['Actual Weight (kg)'] = df['Weight(kg)'] * df['multiplier']
df['Volume (kg)'] = df['Actual Weight (kg)'] * df['Reps']

# ✅ Highlight personal records
exercise_prs = df.groupby('Exercise')['Actual Weight (kg)'].max().to_dict()
df['PR'] = df.apply(lambda row: "🏅" if row['Actual Weight (kg)'] == exercise_prs[row['Exercise']] else "", axis=1)

# --- Sidebar ---
st.sidebar.title("Filters")

view_mode = st.sidebar.radio("📊 View Mode", ["By Date", "By Exercise"])

if view_mode == "By Date":
    unique_days = sorted(df['Day'].unique(), reverse=True)
    
    st.sidebar.markdown("### ⭐ Workout Days")
    for day in unique_days:
        st.sidebar.markdown(f"⭐ {day}")
    
    selected_day = st.sidebar.date_input("📅 Pick a workout date", value=unique_days[0],
                                         min_value=min(unique_days), max_value=max(unique_days))
    
    if selected_day not in unique_days:
        st.warning("No workout data for this date. Please select a valid starred day.")
        st.stop()

    df_view = df[df['Day'] == selected_day]
    view_title = f"Workout for {selected_day}"

else:  # By Exercise
    all_exercises = sorted(df['Exercise'].unique())
    selected_exercise = st.sidebar.selectbox("💪 Select an exercise", all_exercises)
    df_view = df[df['Exercise'] == selected_exercise]
    view_title = f"All Sets for: {selected_exercise}"

# --- Display Results ---
st.header(view_title)

for exercise in df_view['Exercise'].unique():
    st.subheader(f"💪 {exercise}")
    
    df_ex = df_view[df_view['Exercise'] == exercise].sort_values(by='Date').reset_index(drop=True)
    df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1

    columns_to_show = ['Date', 'Set #', 'Reps', 'Weight(kg)', 'multiplier',
                       'Actual Weight (kg)', 'Volume (kg)', 'PR']
    st.dataframe(df_ex[columns_to_show], use_container_width=True)
