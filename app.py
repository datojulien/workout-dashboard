import pandas as pd
import streamlit as st

# Set page and style
st.set_page_config(page_title="Julien's Workout Dashboard", layout="wide")

# Optional light CSS styling
st.markdown("""
    <style>
    .stDataFrame {border: 1px solid #eee; border-radius: 10px;}
    .block-container {padding-top: 1rem;}
    </style>
""", unsafe_allow_html=True)

st.title("🏋️ Julien's Workout Dashboard")
st.markdown("Tracking Julien's sets, volume, and personal bests 🏅. View by day or by exercise.")

# Load CSV from GitHub
csv_url = "https://raw.githubusercontent.com/datojulien/workout-dashboard/main/WorkoutExport.csv"
df = pd.read_csv(csv_url)
df['Date'] = pd.to_datetime(df['Date'])
df['Day'] = df['Date'].dt.date

# Filter out cardio (e.g. Stair Stepper)
df = df[~df['Exercise'].str.contains("Stair Stepper|Cycling|Running", case=False, na=False)]

# Add computed columns
df['Actual Weight (kg)'] = df['Weight(kg)'] * df['multiplier']
df['Volume (kg)'] = df['Actual Weight (kg)'] * df['Reps']

# Highlight PR sets
exercise_prs = df.groupby('Exercise')['Actual Weight (kg)'].max().to_dict()
df['PR'] = df.apply(lambda row: "🏅" if row['Actual Weight (kg)'] == exercise_prs[row['Exercise']] else "", axis=1)

# Sidebar filters
st.sidebar.title("Filters")
view_mode = st.sidebar.radio("📊 View Mode", ["By Date", "By Exercise"])

if view_mode == "By Date":
    # View by workout day
    unique_days = sorted(df['Day'].unique(), reverse=True)
    selected_day = st.sidebar.selectbox("📅 Select a date", unique_days)

    df_view = df[df['Day'] == selected_day]
    summary_title = f"📊 Summary for {selected_day}"

elif view_mode == "By Exercise":
    # View all days for selected exercise
    all_exercises = sorted(df['Exercise'].unique())
    selected_exercise = st.sidebar.selectbox("💪 Select an exercise", all_exercises)

    df_view = df[df['Exercise'] == selected_exercise]
    summary_title = f"📊 Summary for {selected_exercise}"

# ⬇️ Summary Header (Contextual)
total_volume = df_view['Volume (kg)'].sum()
total_sets = len(df_view)
top_lift = df_view['Actual Weight (kg)'].max()

st.markdown(f"### {summary_title}")
cols = st.columns(3)
cols[0].metric("Total Volume", f"{total_volume:,.0f} kg")
cols[1].metric("Total Sets", f"{total_sets}")
cols[2].metric("Heaviest Lift", f"{top_lift:.1f} kg")

# ⬇️ Show tables
if df_view.empty:
    st.info("No workout data found.")
else:
    if view_mode == "By Date":
        for exercise in df_view['Exercise'].unique():
            df_ex = df_view[df_view['Exercise'] == exercise].reset_index(drop=True)
            df_ex['Set #'] = df_ex.groupby(['Day', 'Exercise']).cumcount() + 1
            df_display = df_ex[['Set #', 'Reps', 'Weight(kg)', 'multiplier',
                                'Actual Weight (kg)', 'Volume (kg)', 'PR']]
            with st.expander(f"{exercise}", expanded=True):
                st.markdown(f"### 💪 {exercise}")
                st.dataframe(df_display, use_container_width=True)

    elif view_mode == "By Exercise":
        for day in sorted(df_view['Day'].unique(), reverse=True):
            df_day = df_view[df_view['Day'] == day].reset_index(drop=True)
            df_day['Set #'] = df_day.groupby(['Day', 'Exercise']).cumcount() + 1
            df_display = df_day[['Set #', 'Reps', 'Weight(kg)', 'multiplier',
                                 'Actual Weight (kg)', 'Volume (kg)', 'PR']]
            with st.expander(f"{day}", expanded=True):
                st.markdown(f"### 📅 {day}")
                st.dataframe(df_display, use_container_width=True)
