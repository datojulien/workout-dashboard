import pandas as pd
import streamlit as st
import altair as alt
from datetime import timedelta
from supabase import create_client, Client

st.set_page_config(page_title="Julien's Elite Dashboard", layout="wide")
st.markdown("""<style>
    .stDataFrame {border:1px solid #eee;border-radius:10px;}
    .block-container {padding-top:1rem;}
    .metric-card {background-color: #f0f2f6; padding: 10px; border-radius: 10px;}
</style>""", unsafe_allow_html=True)

# ---------- Connection & Data ---------- #
@st.cache_resource
def init_connection():
    url = st.secrets["connections"]["supabase"]["url"]
    key = st.secrets["connections"]["supabase"]["key"]
    return create_client(url, key)

supabase = init_connection()

@st.cache_data(ttl=600)
def load_data():
    response = supabase.table("workouts") \
        .select("*") \
        .order("date", desc=True) \
        .order("set_order", desc=False) \
        .limit(10000).execute()
    
    data = pd.DataFrame(response.data)
    if data.empty: return data

    data["Date"] = pd.to_datetime(data["date"], errors="coerce", utc=True).dt.tz_localize(None)
    data["Day"] = data["Date"].dt.date
    data["Exercise"] = data["exercise"]
    data["Reps"] = pd.to_numeric(data["reps"], errors='coerce').fillna(0)
    data["Weight_KG"] = pd.to_numeric(data["weight_kg"], errors='coerce').fillna(0)
    data["Multiplier"] = pd.to_numeric(data["multiplier"], errors='coerce').fillna(1)
    data["Set_Order"] = pd.to_numeric(data["set_order"], errors='coerce').fillna(1)
    
    data["Actual Weight (kg)"] = data["Weight_KG"] * data["Multiplier"]
    data["Volume (kg)"] = data["Actual Weight (kg)"] * data["Reps"]
    return data

df = load_data()

# ---------- Advanced Calculations ---------- #
def estimate_1rm(w, r): return w * (1 + r/30) if r > 1 else w

# Calculate 1RM Max for EVERY exercise to determine intensity %
exercise_maxes = df.apply(lambda r: estimate_1rm(r["Actual Weight (kg)"], r["Reps"]), axis=1)
df["1RM_Estimate"] = exercise_maxes
all_time_maxes = df.groupby("Exercise")["1RM_Estimate"].max().to_dict()

# Intensity: How close is this set to your all-time 1RM?
df["Intensity %"] = df.apply(lambda r: (r["1RM_Estimate"] / all_time_maxes.get(r["Exercise"], 1)) * 100 if r["Actual Weight (kg)"] > 0 else 0, axis=1)

# Categorize Workout Type
def classify_exercise(name):
    n = str(name).lower()
    if any(k in n for k in ["squat","leg","lunge","calf","hip thrust","rdl"]): return "Lower"
    if any(k in n for k in ["bench","press","dip","push","tricep"]): return "Push"
    if any(k in n for k in ["row","pull","curl","shrug","chin"]): return "Pull"
    return "Core/Other"

df["Category"] = df["Exercise"].apply(classify_exercise)

# ---------- Sidebar ---------- #
st.sidebar.title("Dashboard Control")
view_mode = st.sidebar.radio("View Mode", ("By Date", "By Exercise"))
weeks = st.sidebar.slider("Trends Horizon (Weeks)", 4, 52, 12)

# ---------- Header Metrics ---------- #
if view_mode == "By Date":
    sel_day = st.sidebar.selectbox("Select Date", sorted(df["Day"].unique(), reverse=True))
    df_sel = df[df["Day"] == sel_day]
    st.title(f"🗓️ Workout: {sel_day}")
else:
    sel_ex = st.sidebar.selectbox("Select Exercise", sorted(df["Exercise"].unique()))
    df_sel = df[df["Exercise"] == sel_ex]
    st.title(f"📈 Progress: {sel_ex}")

# Top Metric Row
m1, m2, m3, m4 = st.columns(4)
total_vol = df_sel['Volume (kg)'].sum()
m1.metric("Total Volume", f"{total_vol:,.0f} kg")
m2.metric("Total Reps", int(df_sel['Reps'].sum()))
m3.metric("Avg Intensity", f"{df_sel[df_sel['Actual Weight (kg)'] > 0]['Intensity %'].mean():.1f}%")
m4.metric("Sets Completed", len(df_sel))

st.divider()

# ---------- Visualizations ---------- #
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Progress Over Time")
    cutoff = pd.Timestamp.today() - timedelta(weeks=weeks)
    trend_data = df[(df["Exercise"] == (sel_ex if view_mode == "By Exercise" else df_sel["Exercise"].iloc[0])) & (df["Date"] >= cutoff)]
    
    if not trend_data.empty:
        # 1RM Trend Chart
        chart_data = trend_data.groupby("Day")["1RM_Estimate"].max().reset_index()
        line = alt.Chart(chart_data).mark_line(point=True, color="#ff4b4b").encode(
            x=alt.X("Day:T", title="Date"),
            y=alt.Y("1RM_Estimate:Q", title="Est. 1RM (kg)", scale=alt.Scale(zero=False))
        ).properties(height=300)
        st.altair_chart(line, use_container_width=True)

with col_right:
    st.subheader("Volume Split")
    # Show volume by body part for the selected day or overall
    pie_data = df_sel.groupby("Category")["Volume (kg)"].sum().reset_index()
    pie = alt.Chart(pie_data).mark_arc().encode(
        theta="Volume (kg):Q",
        color="Category:N"
    ).properties(height=300)
    st.altair_chart(pie, use_container_width=True)



# ---------- The "Work Table" ---------- #
st.subheader("📋 Workout Details")
display_df = df_sel.copy()

# Highlight Top Set
max_vol_idx = display_df["Volume (kg)"].idxmax() if not display_df.empty else None

def highlight_top_set(s):
    return ['background-color: #d4edda' if s.name == max_vol_idx else '' for _ in s]

# Format and clean columns
display_df["Intensity"] = display_df["Intensity %"].map("{:.1f}%".format)
cols = ["Set_Order", "Exercise", "Reps", "Weight_KG", "Multiplier", "Actual Weight (kg)", "Volume (kg)", "Intensity"]

if view_mode == "By Date":
    for ex in df_sel["Exercise"].unique():
        st.write(f"**{ex}**")
        ex_df = display_df[display_df["Exercise"] == ex][cols[2:]] # Drop Set_Order/Ex name for sub-tables
        st.table(ex_df) # Using table for cleaner look on mobile
else:
    st.dataframe(display_df[cols].style.apply(highlight_top_set, axis=1), use_container_width=True, hide_index=True)

# ---------- Training Load Logic ---------- #
st.divider()
st.subheader("🧠 Coach's Corner")
c_1, c_2 = st.columns(2)

with c_1:
    # Acute:Chronic Workload Ratio
    weeks_summary = df.groupby(df['Date'].dt.isocalendar().week)['Volume (kg)'].sum()
    if len(weeks_summary) > 1:
        acute = weeks_summary.iloc[-1]
        chronic = weeks_summary.iloc[-5:-1].mean() if len(weeks_summary) > 4 else weeks_summary.iloc[:-1].mean()
        ratio = acute / chronic if chronic > 0 else 1.0
        
        status = "✅ Optimal" if 0.8 <= ratio <= 1.3 else "⚠️ High Fatigue" if ratio > 1.3 else "📉 Under-training"
        st.metric("Workload Ratio (ACWR)", f"{ratio:.2f}", help="Ideal range is 0.8 - 1.3. Higher means risk of injury.")
        st.write(f"Current Status: **{status}**")

with c_2:
    # Weekly Consistency
    st.metric("Unique Exercises (This Week)", df[df['Date'] >= (pd.Timestamp.today() - timedelta(days=7))]['Exercise'].nunique())
    st.write("Coach Azim's Tip: Focus on increasing the **Intensity %** of your top sets over time rather than just adding more reps.")
