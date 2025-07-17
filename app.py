import pandas as pd
import streamlit as st

# Set up the Streamlit page
st.set_page_config(page_title="🏋️ Workout Dashboard", layout="wide")

st.title("🏋️ Workout Dashboard")
st.markdown("Track your sets, weights, and volume. Personal bests are marked with 🏅")

# Load CSV from GitHub
csv_url = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# Filter out cardio machines like Stair Stepper
df = df[~df['Exercise'].str.contains("Stair Stepper", case=False, na=False)]

# Compute actual weight lifted and volume
df['Actual Weight (kg)'] = df['Weight(kg)'] * df['multiplier']
df['Volume (kg)'] = df['Actual Weight (kg)'] * df['Reps']

# Find personal records (PR) for each exercise
exercise_prs = df.groupby('Exercise')['Actual Weight (kg)'].max().to_dict()
df['PR'] = df.apply(lambda row: "🏅" if row['Actual Weight (kg)'] == exercise_prs[row['Exercise']] else "", axis=1)

# Sidebar filters
unique_days = sorted(df['Day'].unique(), reverse=True)
selected_day = st.sidebar.selectbox("📅 Select a day", unique_days)

exercises = sorted(df[df['Day'] == selected_day]['Exercise'].unique())
exercise_options = ["All"] + exercises
selected_exercise = st.sidebar.selectbox("💪 Filter by exercise", exercise_options)

# Filter dataset by day and optional exercise
df_day = df[df['Day'] == selected_day]
if selected_exercise != "All":
    df_day = df_day[df_day['Exercise'] == selected_exercise]

# Show workout sets
for exercise in df_day['Exercise'].unique():
    st.subheader(f"💪 {exercise}")
    df_ex = df_day[df_day['Exercise'] == exercise].reset_index(drop=True)
    df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1
    
    df_display = df_ex[['Set #', 'Reps', 'Weight(kg)', 'multiplier', 'Actual Weight (kg)', 'Volume (kg)', 'PR']]
    st.dataframe(df_display, use_container_width=True)
