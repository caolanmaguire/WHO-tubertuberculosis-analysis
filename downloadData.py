"""
WHO Tuberculosis Data — Download & Exploratory Analysis
========================================================
Assignment 2: Information Visualisation
Topic: TB re-emergence and its impact on socially deprived parts of the world

HOW TO GET THE DATA (manual downloads required):
─────────────────────────────────────────────────────────────────────────────
The WHO extranet blocks automated downloads. Download these 3 files manually
and place them in the data/raw/ folder before running this script.

1. WHO TB BURDEN ESTIMATES
   → https://www.who.int/teams/global-tuberculosis-programme/data
   Under "CSV files to download" → click "WHO TB burden estimates [>1Mb]"
   Save as: data/raw/who_estimates.csv

2. WHO INCIDENCE BY AGE/SEX/RISK FACTOR
   Same page → "WHO TB incidence estimates disaggregated by age group, sex and risk factor"
   Save as: data/raw/who_estimates_age_sex.csv

3. WORLD BANK GDP PER CAPITA
   → https://data.worldbank.org/indicator/NY.GDP.PCAP.CD
   Click "Download" → CSV → unzip → find the file named API_NY.GDP...csv
   Save as: data/raw/worldbank_gdp.csv
─────────────────────────────────────────────────────────────────────────────
"""

import pandas as pd
import os
import sys
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

# ── Directories ───────────────────────────────────────────────────────────────
for d in ["data/raw", "data/processed", "outputs"]:
    os.makedirs(d, exist_ok=True)

# ── 1. LOAD DATA ──────────────────────────────────────────────────────────────
def load_or_warn(path, name):
    if not os.path.exists(path):
        print(f"\n  ⚠️  Missing: {path}")
        print(f"     See instructions at the top of this script.")
        return None
    df = pd.read_csv(path, encoding="latin1", low_memory=False)
    print(f"  ✓  {name}: {df.shape[0]:,} rows × {df.shape[1]} cols")
    return df

print("=== Loading datasets ===")
est     = load_or_warn("data/raw/who_estimates.csv",        "WHO TB Burden Estimates")
age_sex = load_or_warn("data/raw/who_estimates_age_sex.csv","WHO Incidence by Age/Sex/Risk Factor")
gdp_raw = load_or_warn("data/raw/worldbank_gdp.csv",        "World Bank GDP per Capita")

if est is None:
    print("\n❌  Cannot continue without who_estimates.csv. Download it first.")
    sys.exit(1)

# ── 2. PARSE WORLD BANK GDP ───────────────────────────────────────────────────
# World Bank CSV: first 4 rows are metadata; columns are country, iso3, ..., 1960, 1961, ..., 2023
def parse_worldbank_gdp(path):
    if not path or not os.path.exists(path):
        return None
    df = pd.read_csv(path, skiprows=4, encoding="latin1")
    year_cols = [c for c in df.columns if str(c).strip().isdigit()]
    df = df.melt(
        id_vars=["Country Code"],
        value_vars=year_cols,
        var_name="year",
        value_name="gdp_per_capita"
    ).rename(columns={"Country Code": "iso3"})
    df["year"] = df["year"].astype(int)
    return df.dropna(subset=["gdp_per_capita"])[["iso3", "year", "gdp_per_capita"]]

gdp = parse_worldbank_gdp("data/raw/worldbank_gdp.csv")

# ── 3. COLUMN AUDIT ───────────────────────────────────────────────────────────
print("\n=== Columns in who_estimates.csv ===")
print(list(est.columns))

if age_sex is not None:
    print("\n=== Risk factors available ===")
    if "risk_factor" in age_sex.columns:
        print(age_sex["risk_factor"].dropna().unique())
    else:
        print("  No 'risk_factor' column — columns are:")
        print(list(age_sex.columns))

# ── 4. BUILD CORE DATAFRAME ───────────────────────────────────────────────────
print("\n=== Building core.csv ===")

WANT = [
    "country", "iso3", "g_whoregion", "year",
    "e_inc_100k", "e_inc_100k_lo", "e_inc_100k_hi",  # incidence rate per 100k
    "e_inc_num",                                       # total estimated cases
    "e_mort_100k",                                     # mortality rate (excl HIV-TB)
    "e_mort_tbhiv_100k",                               # mortality rate HIV+TB
    "e_inc_tbhiv_100k",                                # incidence in HIV+ people
    "c_cdr",                                           # case detection / treatment coverage rate
    "e_pop_num",                                       # population estimate
]
core = est[[c for c in WANT if c in est.columns]].copy()

# Attach most-recent GDP per country
if gdp is not None:
    gdp_latest = (
        gdp.sort_values("year", ascending=False)
           .drop_duplicates("iso3")[["iso3", "gdp_per_capita"]]
    )
    core = core.merge(gdp_latest, on="iso3", how="left")
    print(f"  GDP matched: {core['gdp_per_capita'].notna().sum():,} / {len(core):,} rows")
else:
    core["gdp_per_capita"] = None

# World Bank income group thresholds (2023)
INCOME_ORDER = ["Low income", "Lower-middle income", "Upper-middle income", "High income"]

def income_group(g):
    if pd.isna(g):  return "Unknown"
    if g < 1135:    return "Low income"
    if g < 4465:    return "Lower-middle income"
    if g < 13846:   return "Upper-middle income"
    return "High income"

core["income_group"] = core["gdp_per_capita"].apply(income_group)
core.to_csv("data/processed/core.csv", index=False)
print(f"  Saved → data/processed/core.csv  ({len(core):,} rows)")

# ── 5. BUILD RISK FACTOR DATAFRAME ───────────────────────────────────────────
if age_sex is not None and "risk_factor" in age_sex.columns:
    rf_cols = [c for c in [
        "country", "iso3", "g_whoregion", "year", "sex", "age_group",
        "risk_factor", "e_inc_num", "e_inc_num_lo", "e_inc_num_hi"
    ] if c in age_sex.columns]
    rf = age_sex[age_sex["risk_factor"].notna()][rf_cols].copy()
    rf.to_csv("data/processed/risk_factors.csv", index=False)
    print(f"  Saved → data/processed/risk_factors.csv  ({len(rf):,} rows)")

# ── 6. EXPLORATORY PLOTS ─────────────────────────────────────────────────────
print("\n=== Generating exploratory plots ===")

plt.style.use("seaborn-v0_8-whitegrid")
latest_year = int(core["year"].max())
latest      = core[core["year"] == latest_year]

INCOME_COLORS  = ["#c0392b", "#e67e22", "#f39c12", "#2980b9"]
REGION_COLORS  = {
    "AFR": "#c0392b", "SEA": "#e67e22", "WPR": "#f39c12",
    "EMR": "#8e44ad", "EUR": "#2980b9", "AMR": "#27ae60"
}

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle("WHO Tuberculosis Data — Exploratory Overview",
             fontsize=16, fontweight="bold")

# ── Plot 1: Global incidence trend ───────────────────────────────────────────
ax = axes[0, 0]
if "e_inc_num" in core.columns:
    trend = core.groupby("year")["e_inc_num"].sum().reset_index()
    ax.plot(trend["year"], trend["e_inc_num"] / 1e6, color="#c0392b", lw=2.5)
    ax.fill_between(trend["year"], trend["e_inc_num"] / 1e6, alpha=0.12, color="#c0392b")
    ax.axvline(2020, color="grey", ls="--", lw=1.2, label="COVID-19 pandemic")
    ax.legend()
ax.set_title("Global TB Incidence Over Time", fontweight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Estimated cases (millions)")

# ── Plot 2: Incidence rate by WHO region (latest year) ───────────────────────
ax = axes[0, 1]
if "e_inc_100k" in core.columns:
    by_region = (
        latest.groupby("g_whoregion")["e_inc_100k"]
        .median().sort_values(ascending=True)
    )
    colors = ["#2980b9" if v < 50 else "#e67e22" if v < 200 else "#c0392b"
              for v in by_region.values]
    by_region.plot(kind="barh", ax=ax, color=colors)
ax.set_title(f"Median TB Incidence Rate by WHO Region ({latest_year})",
             fontweight="bold")
ax.set_xlabel("Cases per 100,000 population")
ax.set_ylabel("")

# ── Plot 3: Incidence vs GDP scatter ─────────────────────────────────────────
ax = axes[1, 0]
if "gdp_per_capita" in core.columns and "e_inc_100k" in core.columns:
    scatter = latest.dropna(subset=["gdp_per_capita", "e_inc_100k"])
    for region, grp in scatter.groupby("g_whoregion"):
        ax.scatter(
            grp["gdp_per_capita"], grp["e_inc_100k"],
            label=region, alpha=0.65, s=35,
            color=REGION_COLORS.get(region, "grey")
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.legend(title="WHO Region", fontsize=8)
ax.set_title(f"TB Incidence vs GDP per Capita ({latest_year})", fontweight="bold")
ax.set_xlabel("GDP per capita USD (log scale)")
ax.set_ylabel("TB incidence per 100k (log scale)")

# ── Plot 4: Mortality by income group over time ───────────────────────────────
ax = axes[1, 1]
if "e_mort_100k" in core.columns:
    for ig, color in zip(INCOME_ORDER, INCOME_COLORS):
        grp = (
            core[core["income_group"] == ig]
            .groupby("year")["e_mort_100k"]
            .median().reset_index()
        )
        if len(grp):
            ax.plot(grp["year"], grp["e_mort_100k"], label=ig, color=color, lw=2)
    ax.legend(fontsize=8)
ax.set_title("Median TB Mortality Rate by Income Group", fontweight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Deaths per 100,000 population")

plt.tight_layout()
plt.savefig("outputs/01_exploratory_overview.png", dpi=150, bbox_inches="tight")
plt.close()
print("  Saved → outputs/01_exploratory_overview.png")

# ── 7. SUMMARY STATS ──────────────────────────────────────────────────────────
print(f"\n=== Summary stats — {latest_year} ===")
print(f"  Countries: {latest['country'].nunique()}")

if "e_inc_100k" in latest.columns:
    cols = [c for c in ["country", "g_whoregion", "e_inc_100k", "income_group"]
            if c in latest.columns]
    print(f"\n  Top 10 countries by incidence rate:")
    print(latest.nlargest(10, "e_inc_100k")[cols].to_string(index=False))

    print(f"\n  Median incidence per 100k by income group:")
    print(
        latest.groupby("income_group")["e_inc_100k"]
        .median()
        .reindex([g for g in INCOME_ORDER if g in latest["income_group"].values])
        .round(1).to_string()
    )

print("\n✅  Done.")
print("    Processed files → data/processed/")
print("    Exploratory plot → outputs/01_exploratory_overview.png")
print("    Next: build your visualisations in 02_visualisations.py")