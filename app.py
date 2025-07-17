import pandas as pd
import streamlit as st

# Set up the Streamlit page
st.set_page_config(page_title="🏋️ Workout Dashboard", layout="wide")

st.title("🏋️ Workout Dashboard")
st.markdown("Displays your workouts by date and exercise, showing sets, reps, weight, and volume.")

# 👉 REPLACE with your actual GitHub raw CSV link
csv_url = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"

# Load and filter data
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# ❌ Filter out Stair Stepper or other cardio machines
df = df[~df['Exercise'].str.contains("Stair Stepper", case=False, na=False)]

# Sidebar filter: choose a workout day
unique_days = sorted(df['Day'].unique(), reverse=True)
selected_day = st.sidebar.selectbox("📅 Select a day", unique_days)

# Filter by selected day
df_day = df[df['Day'] == selected_day]

# Display workouts per exercise
for exercise in df_day['Exercise'].unique():
    st.subheader(f"💪 {exercise}")
    
    df_ex = df_day[df_day['Exercise'] == exercise].reset_index(drop=True)
    df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1
    
    df_display = df_ex[['Set #', 'Reps', 'Weight(kg)']]
    df_display['Volume (kg)'] = df_display['Reps'] * df_display['Weight(kg)']
    
    st.dataframe(df_display, use_container_width=True)
