import pandas as pd
import streamlit as st

# Set up the Streamlit page
st.set_page_config(page_title="🏋️ Workout Dashboard", layout="wide")

st.title("🏋️ Workout Dashboard")
st.markdown("Displays your workouts by date and exercise, showing sets, reps, weight, and volume.")

# ✅ Your GitHub raw CSV URL
csv_url = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"

# Load and process data
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# ❌ Skip Stair Stepper (or any cardio entries)
df = df[~df['Exercise'].str.contains("Stair Stepper", case=False, na=False)]

# ✅ Calculate Actual Weight (e.g., dumbbell * 2)
df['Actual Weight (kg)'] = df['Weight(kg)'] * df['multiplier']

# ✅ Calculate Volume = Actual Weight × Reps
df['Volume (kg)'] = df['Actual Weight (kg)'] * df['Reps']

# Sidebar: Select workout date
unique_days = sorted(df['Day'].unique(), reverse=True)
selected_day = st.sidebar.selectbox("📅 Select a day", unique_days)

# Filter data for selected day
df_day = df[df['Day'] == selected_day]

# Display each exercise's sets
for exercise in df_day['Exercise'].unique():
    st.subheader(f"💪 {exercise}")
    
    df_ex = df_day[df_day['Exercise'] == exercise].reset_index(drop=True)
    df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1

    df_display = df_ex[['Set #', 'Reps', 'Weight(kg)', 'multiplier', 'Actual Weight (kg)', 'Volume (kg)']]
    st.dataframe(df_display, use_container_width=True)
