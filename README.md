# 🏋️ Workout Dashboard

A clean, interactive Streamlit dashboard to track your workouts — including sets, reps, weights, volume, and personal records — directly from your exported CSV file.

---

## 📌 Features

- ✅ View workouts **by date** or **by exercise**
- ✅ Automatically calculates:
  - **Actual Weight Lifted** (with multiplier)
  - **Total Volume**
  - **Personal Records** 🏅
- ✅ Collapsible sections per exercise or date (open by default)
- ✅ Contextual summary metrics: total volume, total sets, top lift
- ✅ Clean and minimalist UI with professional theme

---


## 🚀 How to Use

### 1. Fork or clone the repository

```bash
git clone https://github.com/datojulien/workout-dashboard.git
cd workout-dashboard
````

### 2. Install dependencies

Make sure you have Python 3.8+ and [Streamlit](https://streamlit.io/) installed:

```bash
pip install streamlit pandas
```

### 3. Run the app locally

```bash
streamlit run app.py
```

---

## 🌐 Deploy on Streamlit Cloud

1. Upload your CSV file (`WorkoutExport.csv`) to the repo
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud)
3. Connect your GitHub account
4. Click “New app” → select this repo → set `app.py` as the main file
5. Click **Deploy**

---

## 📁 CSV Format (Required)

Your `WorkoutExport.csv` should have the following headers:

```
Date,Exercise,Reps,Weight(kg),Duration(s),Distance(m),Incline,Resistance,isWarmup,Note,multiplier
```

Example row:

```
2025-07-16 09:09:40,Dumbbell Row,5,31.75,0,0,0,0,FALSE,,2
```

---

## ⚙️ Customization

* **Exclude cardio exercises** like Stair Stepper or Cycling:

  ```python
  df = df[~df['Exercise'].str.contains("Stair Stepper|Cycling", case=False, na=False)]
  ```

* **Change theme colors** via `.streamlit/config.toml`.

---

## 📄 License

MIT License © [Julien](https://github.com/datojulien)

```

---

Let me know if you want:
- A French version of the README
- Screenshot or preview image guidance
- Instructions to enable the mobile layout feature in the future
```
