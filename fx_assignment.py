import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import warnings

warnings.filterwarnings("ignore")
plt.style.use("seaborn-v0_8-whitegrid")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def sharpe_ratio(returns, periods_per_year):
    if returns.std() == 0:
        return 0.0
    return returns.mean() / returns.std() * np.sqrt(periods_per_year)


def max_drawdown(cum_returns):
    peak = cum_returns.cummax()
    dd = (cum_returns - peak) / peak
    return dd.min()


def hit_rate(returns):
    nonzero = returns[returns != 0]
    if len(nonzero) == 0:
        return 0.0
    return (nonzero > 0).mean()


# ============================================================
# PART A: BASIC BALANCE / DOLLAR INDEX STRATEGY
# ============================================================
print("=" * 70)
print("ASSIGNMENT 5A: BASIC BALANCE / DOLLAR INDEX STRATEGY")
print("=" * 70)

# --- Parse Basic Balance data ---
bb_path = os.path.join(BASE_DIR, "assignment_basic_balance_data.xlsx - Basic Balance.csv")
bb_raw = pd.read_csv(bb_path, header=0)

dates = pd.to_datetime(bb_raw.iloc[:, 0], format="%Y-%m")
twi = pd.to_numeric(bb_raw.iloc[:, 1], errors="coerce")
ln_twi = pd.to_numeric(bb_raw.iloc[:, 2], errors="coerce")
basic_balance = pd.to_numeric(bb_raw.iloc[:, 11], errors="coerce")

bb_df = pd.DataFrame({
    "date": dates,
    "TWI": twi.values,
    "ln_TWI": ln_twi.values,
    "BasicBalance": basic_balance.values,
}).set_index("date")

# Recompute ln(TWI) for precision
bb_df["ln_TWI"] = np.log(bb_df["TWI"])

# Monthly dollar return = change in ln(TWI) over the next month
bb_df["dollar_return"] = bb_df["ln_TWI"].shift(-1) - bb_df["ln_TWI"]

print(f"\nBasic Balance data: {len(bb_df)} months ({bb_df.index[0].strftime('%Y-%m')} to {bb_df.index[-1].strftime('%Y-%m')})")
print(f"Basic Balance available from: {bb_df['BasicBalance'].first_valid_index().strftime('%Y-%m')}")
print(f"TWI available from: {bb_df['TWI'].first_valid_index().strftime('%Y-%m')}")

# --- Build strategy for T=1..6 ---
A = 4.54
BETA = 0.000871

results_by_lag = {}

for T in range(1, 7):
    df = bb_df.copy()
    df["BB_lagged"] = df["BasicBalance"].shift(T)
    df["predicted_ln_TWI"] = BETA * df["BB_lagged"] + A
    df["signal"] = np.where(
        df["predicted_ln_TWI"] > df["ln_TWI"], 1,
        np.where(df["predicted_ln_TWI"] < df["ln_TWI"], -1, 0)
    )
    df["strategy_return"] = df["signal"] * df["dollar_return"]

    valid = df.dropna(subset=["strategy_return", "signal", "BB_lagged"])
    valid = valid[valid["signal"] != 0]

    cum_ret = (1 + valid["strategy_return"]).cumprod()

    results_by_lag[T] = {
        "valid": valid,
        "cum_ret": cum_ret,
        "total_return": cum_ret.iloc[-1] - 1 if len(cum_ret) > 0 else 0,
        "sharpe": sharpe_ratio(valid["strategy_return"], 12),
        "hit": hit_rate(valid["strategy_return"]),
        "mdd": max_drawdown(cum_ret),
        "n_months": len(valid),
    }

# --- Lag analysis summary ---
print("\n--- Lag Analysis (T = 1 to 6) ---")
print(f"{'Lag T':<8}{'Total Ret':>12}{'Sharpe':>10}{'Hit Rate':>10}{'Max DD':>10}{'# Months':>10}")
print("-" * 60)
for T in range(1, 7):
    r = results_by_lag[T]
    print(f"  {T:<6}{r['total_return']:>11.2%}{r['sharpe']:>10.3f}{r['hit']:>10.1%}{r['mdd']:>10.2%}{r['n_months']:>10d}")

best_lag = max(results_by_lag, key=lambda t: results_by_lag[t]["sharpe"])
print(f"\nBest lag by Sharpe ratio: T = {best_lag} (Sharpe = {results_by_lag[best_lag]['sharpe']:.3f})")

# --- Equity curve plot for all lags ---
fig, ax = plt.subplots(figsize=(12, 6))
for T in range(1, 7):
    cr = results_by_lag[T]["cum_ret"]
    ax.plot(cr.index, cr.values, label=f"T={T} (Sharpe={results_by_lag[T]['sharpe']:.2f})")
ax.set_title("Assignment 5A: Equity Curves by Lag (T=1 to 6)")
ax.set_ylabel("Cumulative Return (Growth of $1)")
ax.set_xlabel("Date")
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "5A_equity_curves_by_lag.png"), dpi=150)
plt.close(fig)
print(f"\nSaved: output/5A_equity_curves_by_lag.png")

# --- Threshold sensitivity analysis (using best lag) ---
thresholds = np.arange(0, 0.051, 0.005)
threshold_results = []

df_best = bb_df.copy()
df_best["BB_lagged"] = df_best["BasicBalance"].shift(best_lag)
df_best["predicted_ln_TWI"] = BETA * df_best["BB_lagged"] + A
df_best["diff"] = df_best["predicted_ln_TWI"] - df_best["ln_TWI"]

for thresh in thresholds:
    df_t = df_best.copy()
    df_t["signal"] = np.where(
        df_t["diff"] > thresh, 1,
        np.where(df_t["diff"] < -thresh, -1, 0)
    )
    df_t["strategy_return"] = df_t["signal"] * df_t["dollar_return"]
    valid = df_t.dropna(subset=["strategy_return", "BB_lagged"])

    invested = (valid["signal"] != 0)
    strat_rets = valid.loc[invested, "strategy_return"]

    if len(strat_rets) > 0:
        cum = (1 + valid["strategy_return"]).cumprod()
        sr = sharpe_ratio(strat_rets, 12)
        total = cum.iloc[-1] - 1
        mdd = max_drawdown(cum)
        hr = hit_rate(strat_rets)
        pct_invested = invested.mean()
    else:
        sr = total = mdd = hr = 0.0
        pct_invested = 0.0

    threshold_results.append({
        "threshold": thresh,
        "total_return": total,
        "sharpe": sr,
        "hit_rate": hr,
        "max_dd": mdd,
        "pct_invested": pct_invested,
    })

thresh_df = pd.DataFrame(threshold_results)

print(f"\n--- Threshold Sensitivity Analysis (T = {best_lag}) ---")
print(f"{'Threshold':<12}{'Total Ret':>12}{'Sharpe':>10}{'Hit Rate':>10}{'Max DD':>10}{'% Invested':>12}")
print("-" * 66)
for _, row in thresh_df.iterrows():
    print(f"  {row['threshold']:<10.3f}{row['total_return']:>11.2%}{row['sharpe']:>10.3f}"
          f"{row['hit_rate']:>10.1%}{row['max_dd']:>10.2%}{row['pct_invested']:>11.1%}")

fig, axes = plt.subplots(1, 3, figsize=(16, 5))

axes[0].plot(thresh_df["threshold"], thresh_df["sharpe"], "o-", color="steelblue")
axes[0].set_title("Sharpe Ratio vs. Threshold")
axes[0].set_xlabel("Threshold")
axes[0].set_ylabel("Sharpe Ratio")

axes[1].plot(thresh_df["threshold"], thresh_df["total_return"] * 100, "o-", color="green")
axes[1].set_title("Total Return vs. Threshold")
axes[1].set_xlabel("Threshold")
axes[1].set_ylabel("Total Return (%)")

axes[2].plot(thresh_df["threshold"], thresh_df["pct_invested"] * 100, "o-", color="darkorange")
axes[2].set_title("% Time Invested vs. Threshold")
axes[2].set_xlabel("Threshold")
axes[2].set_ylabel("% Invested")

fig.suptitle(f"Assignment 5A: Threshold Sensitivity (T = {best_lag})", fontsize=13, y=1.02)
fig.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "5A_threshold_sensitivity.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\nSaved: output/5A_threshold_sensitivity.png")

# --- 5A Commentary ---
print("\n--- 5A Commentary ---")
print(f"""
The Deutsche Bank model ln(TWI) = 0.000871 * BasicBalance(t-T) + 4.54 is tested
with lags T = 1 through 6. The decision rule goes long the dollar when the model
predicts a higher value than the actual ln(TWI), and short otherwise.

Best performing lag: T = {best_lag} based on Sharpe ratio ({results_by_lag[best_lag]['sharpe']:.3f}).
The article claims that T = 6 (six-month lag) best predicts the dollar index.
Our results show T = {best_lag} has the best risk-adjusted returns. Note that T = 1
is not actually tradable since Basic Balance data is released with a ~6 week delay.

Threshold analysis shows that requiring a minimum difference between predicted and
actual values before trading can improve the Sharpe ratio by filtering out marginal
signals, though it reduces the number of trades. The strategy transitions from a
two-state (Long/Short) to a three-state (Long/Short/Neutral) model.
""")


# ============================================================
# PART B: CARRY TRADE STRATEGY
# ============================================================
print("\n" + "=" * 70)
print("ASSIGNMENT 5B: CARRY TRADE STRATEGY")
print("=" * 70)

# --- Parse carry trade data ---
carry_path = os.path.join(BASE_DIR, "assignment_carry_data.xlsx - Sheet1.csv")
carry_raw = pd.read_csv(carry_path, skiprows=3, header=None)

col_names = [
    "date", "US_rate", "Brit_rate", "Canada_rate", "Euro_rate", "Japan_rate", "Swiss_rate", "Aussie_rate",
    "ret_Brit", "ret_Canada", "ret_Euro", "ret_Japan", "ret_Swiss", "ret_Aussie",
    "diff_USBrit", "diff_USCan", "diff_USEuro", "diff_USJapan", "diff_USSwiss", "diff_USAussie",
    "out_BP", "out_Canada", "out_Euro", "out_Japan", "out_Swiss", "out_Aussie", "out_Overall", "out_EQ",
]
carry_raw.columns = col_names[:len(carry_raw.columns)]

carry_df = pd.DataFrame()
carry_df["date"] = pd.to_datetime(carry_raw["date"].astype(str), format="mixed")
carry_df = carry_df.set_index("date")

carry_df["US_rate"] = pd.to_numeric(carry_raw["US_rate"].values, errors="coerce")

currencies = ["Brit", "Canada", "Euro", "Japan", "Swiss", "Aussie"]
currency_labels = {
    "Brit": "British Pound",
    "Canada": "Canadian Dollar",
    "Euro": "Euro",
    "Japan": "Japanese Yen",
    "Swiss": "Swiss Franc",
    "Aussie": "Australian Dollar",
}

for ccy in currencies:
    carry_df[f"{ccy}_rate"] = pd.to_numeric(carry_raw[f"{ccy}_rate"].values, errors="coerce")
    carry_df[f"ret_{ccy}"] = pd.to_numeric(carry_raw[f"ret_{ccy}"].values, errors="coerce")

carry_df = carry_df.dropna(subset=["US_rate"])

print(f"\nCarry trade data: {len(carry_df)} days ({carry_df.index[0].strftime('%Y-%m-%d')} to {carry_df.index[-1].strftime('%Y-%m-%d')})")

# --- Build carry strategy per currency ---
for ccy in currencies:
    rate_diff = carry_df[f"{ccy}_rate"] - carry_df["US_rate"]
    carry_df[f"pos_{ccy}"] = np.where(rate_diff > 0, 1, np.where(rate_diff < 0, -1, 0))
    carry_df[f"strat_ret_{ccy}"] = carry_df[f"pos_{ccy}"] * carry_df[f"ret_{ccy}"] / 100

# Portfolio: equal-weight average across all 6 currencies
strat_cols = [f"strat_ret_{ccy}" for ccy in currencies]
carry_df["strat_ret_portfolio"] = carry_df[strat_cols].mean(axis=1)

# --- Per-currency and portfolio analysis ---
print("\n--- Carry Trade Base Strategy (Threshold = 0) ---")
print(f"{'Currency':<22}{'Total Ret':>12}{'Ann. Sharpe':>12}{'Hit Rate':>10}{'Max DD':>10}")
print("-" * 66)

carry_stats = {}
for ccy in currencies + ["portfolio"]:
    col = f"strat_ret_{ccy}"
    rets = carry_df[col].dropna()
    cum = (1 + rets).cumprod()
    s = sharpe_ratio(rets, 252)
    tr = cum.iloc[-1] - 1
    mdd_val = max_drawdown(cum)
    hr = hit_rate(rets)
    label = currency_labels.get(ccy, "Portfolio (EW)")
    carry_stats[ccy] = {"cum_ret": cum, "sharpe": s, "total_return": tr, "mdd": mdd_val, "hit": hr}
    print(f"  {label:<20}{tr:>11.2%}{s:>12.3f}{hr:>10.1%}{mdd_val:>10.2%}")

# --- Equity curve plot ---
fig, axes = plt.subplots(2, 1, figsize=(14, 10))

for ccy in currencies:
    cr = carry_stats[ccy]["cum_ret"]
    axes[0].plot(cr.index, cr.values, label=currency_labels[ccy], alpha=0.8)
axes[0].set_title("Carry Trade: Per-Currency Equity Curves")
axes[0].set_ylabel("Growth of $1")
axes[0].legend(fontsize=8)

cr_port = carry_stats["portfolio"]["cum_ret"]
axes[1].plot(cr_port.index, cr_port.values, color="navy", linewidth=2)
axes[1].set_title(f"Carry Trade: Equal-Weight Portfolio (Sharpe={carry_stats['portfolio']['sharpe']:.2f})")
axes[1].set_ylabel("Growth of $1")
axes[1].set_xlabel("Date")

fig.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "5B_carry_equity_curves.png"), dpi=150)
plt.close(fig)
print(f"\nSaved: output/5B_carry_equity_curves.png")

# --- Threshold sensitivity analysis (0 to 0.5%) ---
carry_thresholds = np.arange(0, 0.55, 0.05)
carry_thresh_results = []

for thresh in carry_thresholds:
    pos_arrays = []

    for ccy in currencies:
        rate_diff = carry_df[f"{ccy}_rate"] - carry_df["US_rate"]
        pos = np.where(
            rate_diff > thresh, 1,
            np.where(rate_diff < -thresh, -1, 0)
        )
        pos_arrays.append(pos)

    pos_matrix = np.array(pos_arrays)
    active_count = (pos_matrix != 0).sum(axis=0)
    pct_inv = (active_count > 0).mean()

    ret_arrays = []
    for i, ccy in enumerate(currencies):
        strat_ret = pos_arrays[i] * carry_df[f"ret_{ccy}"].values / 100
        ret_arrays.append(strat_ret)

    port_rets = np.nanmean(ret_arrays, axis=0)
    port_series = pd.Series(port_rets, index=carry_df.index)
    cum = (1 + port_series).cumprod()

    nonzero_mask = port_series.abs() > 1e-12
    invested_rets = port_series[nonzero_mask]

    if len(invested_rets) > 0:
        sr = sharpe_ratio(port_series, 252)
        total = cum.iloc[-1] - 1
        mdd_val = max_drawdown(cum)
        hr = hit_rate(invested_rets)
    else:
        sr = total = mdd_val = hr = 0.0

    avg_pairs_active = active_count.mean() / len(currencies)

    carry_thresh_results.append({
        "threshold": thresh,
        "total_return": total,
        "sharpe": sr,
        "hit_rate": hr,
        "max_dd": mdd_val,
        "pct_invested": avg_pairs_active,
    })

ct_df = pd.DataFrame(carry_thresh_results)

print(f"\n--- Carry Trade Threshold Sensitivity (0 to 0.5%) ---")
print(f"{'Threshold':<12}{'Total Ret':>12}{'Sharpe':>10}{'Hit Rate':>10}{'Max DD':>10}{'% Invested':>12}")
print("-" * 66)
for _, row in ct_df.iterrows():
    print(f"  {row['threshold']:<10.2f}{row['total_return']:>11.2%}{row['sharpe']:>10.3f}"
          f"{row['hit_rate']:>10.1%}{row['max_dd']:>10.2%}{row['pct_invested']:>11.1%}")

fig, axes = plt.subplots(1, 3, figsize=(16, 5))

axes[0].plot(ct_df["threshold"], ct_df["sharpe"], "o-", color="steelblue")
axes[0].set_title("Sharpe Ratio vs. Threshold")
axes[0].set_xlabel("Rate Differential Threshold (%)")
axes[0].set_ylabel("Sharpe Ratio")

axes[1].plot(ct_df["threshold"], ct_df["total_return"] * 100, "o-", color="green")
axes[1].set_title("Total Return vs. Threshold")
axes[1].set_xlabel("Rate Differential Threshold (%)")
axes[1].set_ylabel("Total Return (%)")

axes[2].plot(ct_df["threshold"], ct_df["pct_invested"] * 100, "o-", color="darkorange")
axes[2].set_title("% Time Invested vs. Threshold")
axes[2].set_xlabel("Rate Differential Threshold (%)")
axes[2].set_ylabel("% Invested")

fig.suptitle("Assignment 5B: Carry Trade Threshold Sensitivity", fontsize=13, y=1.02)
fig.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "5B_carry_threshold_sensitivity.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\nSaved: output/5B_carry_threshold_sensitivity.png")

# --- 5B Commentary ---
print("\n--- 5B Commentary ---")
print(f"""
The carry trade strategy goes long a foreign currency when its target rate exceeds
the US target rate, and short otherwise. Returns come solely from daily FX moves;
funding costs (the actual interest differential income) are ignored per instructions.

Portfolio Sharpe: {carry_stats['portfolio']['sharpe']:.3f}
Portfolio Total Return: {carry_stats['portfolio']['total_return']:.2%}
Portfolio Max Drawdown: {carry_stats['portfolio']['mdd']:.2%}

Assessment:
- The carry trade exhibits periods of steady gains punctuated by sharp drawdowns,
  consistent with the well-known "picking up pennies in front of a steamroller"
  characterization. The GFC (2008) likely caused major losses as risk-off flows
  unwound carry positions.
- Diversifying across 6 currency pairs helps smooth returns compared to any
  single pair.
- Introducing a threshold (requiring rate differentials to exceed, say, 0.25-0.50%)
  filters out marginal trades where the carry advantage is small relative to
  FX volatility risk. This can improve risk-adjusted returns but reduces
  the number of active trading days.
- The strategy's performance depends heavily on the macro regime: it tends to
  work well during periods of stable growth and low volatility, and poorly
  during financial crises when currencies reprice sharply.
""")

print("=" * 70)
print("ALL DONE. Charts saved to output/ folder.")
print("=" * 70)
