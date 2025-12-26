import pandas as pd
import streamlit as st
import altair as alt
from datetime import timedelta
from supabase import create_client, Client

# ---------- Page Configuration ---------- #
st.set_page_config(page_title="Julien's Elite Dashboard", layout="wide")
st.markdown("""<style>
    .stDataFrame {border:1px solid #eee; border-radius:10px;}
    .block-container {padding-top:1rem;}
    h3 {font-size: 1.4rem; font-weight: bold;}
    div[data-testid="stMetricValue"] {font-size: 1.8rem;}
</style>""", unsafe_allow_html=True)

st.title("🏋️ Julien's Workout Dashboard")
st.markdown("Tracking sets, volume, intensity, and personal bests 🏅.")

# ---------- Supabase Connection ---------- #
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["connections"]["supabase"]["url"]
        key = st.secrets["connections"]["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error("Missing Secrets! Ensure url and key are set in Streamlit Cloud.")
        st.stop()

supabase = init_connection()

# ---------- Load & Process Data ---------- #
@st.cache_data(ttl=600)
def load_data():
    # 1. Fetch Data: Sort by Date (newest) AND Set Order (1, 2, 3...)
    response = supabase.table("workouts") \
        .select("*") \
        .order("date", desc=True) \
        .order("set_order", desc=False) \
        .limit(10000).execute()
    
    data = pd.DataFrame(response.data)
    if data.empty: return data

    # 2. Type Conversion
    data["Date"] = pd.to_datetime(data["date"], errors="coerce", utc=True).dt.tz_localize(None)
    data["Day"] = data["Date"].dt.date
    data["Exercise"] = data["exercise"]
    data["Reps"] = pd.to_numeric(data["reps"], errors='coerce').fillna(0)
    data["Weight_Single_KG"] = pd.to_numeric(data["weight_kg"], errors='coerce').fillna(0)
    data["Multiplier"] = pd.to_numeric(data["multiplier"], errors='coerce').fillna(1)
    data["Set_Order"] = pd.to_numeric(data["set_order"], errors='coerce').fillna(1)
    
    # 3. Filtering
    data = data.dropna(subset=["Day"])
    data = data[~data["Exercise"].str.contains("Stair Stepper|Cycling", case=False, na=False)]

    # 4. Derived Metrics
    data["Actual Weight (kg)"] = data["Weight_Single_KG"] * data["Multiplier"]
    data["Volume (kg)"] = data["Actual Weight (kg)"] * data["Reps"]
    
    return data

df = load_data()

if df.empty:
    st.warning("No data found in Supabase.")
    st.stop()

# ---------- Calculations & Logic ---------- #

# 1. Epley 1RM Formula
def estimate_1rm(weight, reps):
    return weight * (1 + reps/30) if reps and reps > 1 else weight

df["1RM_Estimate"] = df.apply(lambda r: estimate_1rm(r["Actual Weight (kg)"], r["Reps"]), axis=1)

# 2. PR Detection (Gold Medals)
def assign_prs(data):
    # Heaviest weight lifted for weighted exercises
    prs_w = data[data["Actual Weight (kg)"] > 0].groupby("Exercise")["Actual Weight (kg)"].max().to_dict()
    # Max reps for bodyweight exercises (0kg)
    prs_r = data[data["Actual Weight (kg)"] == 0].groupby("Exercise")["Reps"].max().to_dict()
    
    data["PR"] = data.apply(
        lambda r: (
            "🏅" if (
                (r["Actual Weight (kg)"] > 0 and r["Actual Weight (kg)"] == prs_w.get(r["Exercise"], 0)) or
                (r["Actual Weight (kg)"] == 0 and r["Reps"] == prs_r.get(r["Exercise"], -1))
            ) else ""
        ),
        axis=1
    )
    return data

df = assign_prs(df)

# 3. Workout Classification (Push/Pull/Lower)
def classify_exercise(name):
    n = str(name).lower()
    lowers = ["squat","deadlift","lunge","leg","hamstring","calf","hip thrust","thrust","glute","rdl","good morning"]
    pushes = ["bench","overhead press","shoulder press","incline","dip","push","tricep","pec"]
    pulls = ["row","pulldown","pull-up","curl","face pull","shrug","chin","lat"]
    if any(k in n for k in lowers): return "Lower"
    if any(k in n for k in pushes): return "Push"
    if any(k in n for k in pulls): return "Pull"
    return "Other"

df["Category"] = df["Exercise"].apply(classify_exercise)

# 4. Intensity Calculation (Relative to All-Time Max)
all_time_maxes = df.groupby("Exercise")["1RM_Estimate"].max().to_dict()
df["Intensity %"] = df.apply(
    lambda r: (r["1RM_Estimate"] / all_time_maxes.get(r["Exercise"], 1)) * 100 
    if r["Actual Weight (kg)"] > 0 else 0, 
    axis=1
)

# 5. Weekly Summary Aggregation
df["Week"] = df["Date"].dt.isocalendar().week
weekly_summary = (
    df.groupby("Week", as_index=False)
      .agg({
          "Volume (kg)": "sum",
          "Actual Weight (kg)": "max",
          "Reps": "sum",
          "Exercise": "nunique"
      })
      .rename(columns={
          "Volume (kg)": "Total Volume",
          "Actual Weight (kg)": "Heaviest Lift",
          "Reps": "Total Reps",
          "Exercise": "Unique Exercises"
      })
      .sort_values("Week", ascending=False)
)

# ---------- Sidebar & Filters ---------- #
st.sidebar.title("Filters & Settings")
view_mode = st.sidebar.radio("View Mode", ("By Date", "By Exercise"))
hide_light = st.sidebar.checkbox("Azim View™ – Hide <40kg sets")
weeks_count = st.sidebar.slider("Trend Horizon (Weeks)", 2, 52, 12)

# Debug Info
st.sidebar.divider()
st.sidebar.caption(f"Total Rows: {len(df)}")
st.sidebar.caption(f"Latest Data: {df['Day'].max()}")

# ---------- Selection Logic ---------- #
if view_mode == "By Date":
    days = sorted(df["Day"].unique(), reverse=True)
    sel_day = st.sidebar.selectbox("Select a date", days)
    df_sel = df[df["Day"] == sel_day].copy()
    
    # Get workout name from notes if available
    workout_name = df_sel["note"].iloc[0] if not df_sel.empty and df_sel["note"].iloc[0] else "Workout"
    title = f"🗓️ {sel_day} | {workout_name}"
else:
    exercises = sorted(df["Exercise"].unique())
    sel_ex = st.sidebar.selectbox("Select an exercise", exercises)
    df_sel = df[df["Exercise"] == sel_ex].copy()
    title = f"📈 {sel_ex}"

# Apply "Azim View" Filter
if hide_light:
    df_sel = df_sel[df_sel["Actual Weight (kg)"] >= 40]

# ---------- Dashboard Header Metrics ---------- #
st.header(title)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Volume", f"{df_sel['Volume (kg)'].sum():,.0f} kg")
c2.metric("Total Sets", len(df_sel))
c3.metric("Heaviest Lift", f"{df_sel['Actual Weight (kg)'].max():.1f} kg" if not df_sel.empty else "—")
avg_int = df_sel[df_sel['Actual Weight (kg)'] > 0]['Intensity %'].mean()
c4.metric("Avg Intensity", f"{avg_int:.1f}%" if not pd.isna(avg_int) else "0%")

# ---------- Weekly Summary (Expander) ---------- #
with st.expander("Weekly Summary (Last 4 Weeks)"):
    st.dataframe(weekly_summary.head(4), use_container_width=True, hide_index=True)

# ---------- Visualizations ---------- #
st.subheader("Analysis")
col_chart, col_pie = st.columns([2, 1])

with col_chart:
    # 1RM Trend Chart
    cutoff = pd.Timestamp.today() - timedelta(weeks=weeks_count)
    target_ex = sel_ex if view_mode == "By Exercise" else (df_sel["Exercise"].iloc[0] if not df_sel.empty else None)
    
    if target_ex:
        trend_data = df[(df["Exercise"] == target_ex) & (df["Date"] >= cutoff)]
        if not trend_data.empty:
            chart_data = trend_data.groupby("Day")["1RM_Estimate"].max().reset_index()
            chart = alt.Chart(chart_data).mark_line(point=True, color="#ff4b4b").encode(
                x=alt.X("Day:T", title="Date", axis=alt.Axis(format="%b %d")),
                y=alt.Y("1RM_Estimate:Q", title="Est. 1RM (kg)", scale=alt.Scale(zero=False)),
                tooltip=["Day", alt.Tooltip("1RM_Estimate", format=".1f")]
            ).properties(height=300, title=f"Strength Progression: {target_ex}")
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Select an exercise to see trends.")

with col_pie:
    # Volume Split Pie Chart
    pie_data = df_sel.groupby("Category")["Volume (kg)"].sum().reset_index()
    pie = alt.Chart(pie_data).mark_arc(innerRadius=50).encode(
        theta=alt.Theta("Volume (kg)", stack=True),
        color=alt.Color("Category", scale=alt.Scale(scheme='category10')),
        tooltip=["Category", "Volume (kg)"]
    ).properties(height=300, title="Volume Distribution")
    st.altair_chart(pie, use_container_width=True)

# ---------- Coach's Corner (ACWR) ---------- #
st.divider()
if len(weekly_summary) >= 2:
    acute = weekly_summary["Total Volume"].iloc[0] # Current week
    # Calculate chronic load (avg of previous 4 weeks)
    chronic_series = weekly_summary["Total Volume"].iloc[1:5]
    chronic = chronic_series.mean() if not chronic_series.empty else 0
    
    if chronic > 0:
        ratio = acute / chronic
        c_1, c_2 = st.columns([1, 3])
        c_1.metric("ACWR Score", f"{ratio:.2f}")
        
        status_msg = ""
        if 0.8 <= ratio <= 1.3:
            status_msg = "✅ **Optimal Zone**: Low injury risk, good progression."
        elif ratio > 1.3:
            status_msg = "⚠️ **High Fatigue**: You are increasing volume too quickly (>30% jump)."
        else:
            status_msg = "📉 **Deload / Undertraining**: Volume is significantly lower than usual."
        
        c_2.markdown(f"**Workload Ratio Status:**\n\n{status_msg}")

# ---------- Detailed Tables (Human Readable) ---------- #
st.divider()
st.subheader("📋 Detailed Log")

# Prepare the display dataframe
display_df = df_sel.copy()

# Format Intensity as string percentage
display_df["Intensity"] = display_df["Intensity %"].map("{:.0f}%".format)

# Rename columns for human readability
column_mapping = {
    "Reps": "Reps",
    "Weight_Single_KG": "Weight (1 Unit)",
    "Actual Weight (kg)": "Total Load",
    "Volume (kg)": "Volume",
    "Intensity": "Intensity",
    "PR": "PR",
    "set_order": "Set Order" # Kept for internal sorting, hidden later
}
display_df = display_df.rename(columns=column_mapping)

# Define columns to show
cols_to_show = ["Reps", "Weight (1 Unit)", "Total Load", "Volume", "Intensity", "PR"]

if view_mode == "By Date":
    # Group by exercise for cleaner daily view
    for ex in df_sel["Exercise"].unique():
        st.caption(f"**{ex}**")
        # Filter for this exercise
        ex_df = display_df[display_df["Exercise"] == ex]
        # Sort by the hidden set_order column
        ex_df = ex_df.sort_values("Set Order")
        # Display nicely formatted table without index
        st.dataframe(
            ex_df[cols_to_show].style.format({
                "Total Load": "{:.1f} kg",
                "Weight (1 Unit)": "{:.1f} kg",
                "Volume": "{:,.0f}"
            }), 
            use_container_width=True, 
            hide_index=True
        )
else:
    # By Exercise Mode: Show Date column too
    display_df = display_df.sort_values(["Date", "Set Order"], ascending=[False, True])
    final_cols = ["Day"] + cols_to_show
    st.dataframe(
        display_df[final_cols].style.format({
            "Total Load": "{:.1f} kg",
            "Weight (1 Unit)": "{:.1f} kg",
            "Volume": "{:,.0f}"
        }), 
        use_container_width=True, 
        hide_index=True
    )

# ---------- Download Data ---------- #
st.divider()
st.download_button(
    "📥 Download Full Database (CSV)", 
    df.to_csv(index=False).encode("utf-8"), 
    "julien_workouts_full.csv", 
    "text/csv"
)
