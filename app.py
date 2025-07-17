import pandas as pd
import streamlit as st

# Set up the page
st.set_page_config(page_title="Workout Dashboard", layout="wide")

st.title("🏋️ Workout Dashboard")
st.markdown("Displays exercises, sets, reps, and weights from your workout log.")

# URL of your CSV file on GitHub (raw view)
csv_url = "https://raw.githubusercontent.com/datojulien/Yworkout-dashboard/main/WorkoutExport.csv"

# Load and process data
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# Sidebar filter
unique_days = sorted(df['Day'].unique(), reverse=True)
selected_day = st.sidebar.selectbox("Select a day", unique_days)

df_day = df[df['Day'] == selected_day]

for exercise in df_day['Exercise'].unique():
    st.subheader(exercise)
    df_ex = df_day[df_day['Exercise'] == exercise].reset_index(drop=True)
    df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1
    df_display = df_ex[['Set #', 'Reps', 'Weight(kg)']]
    df_display['Volume (kg)'] = df_display['Reps'] * df_display['Weight(kg)']
    st.dataframe(df_display, use_container_width=True)
