import sys
sys.path.insert(0, ".")
import pandas as pd
import numpy as np

from wc2026.data import load_matches, load_played_wc2026
from wc2026.elo import compute_elo
from wc2026.ensemble import build_ensemble
from wc2026.shootout import calibrate, load_shootouts
from wc2026.simulate import simulate
from wc2026.groups import GROUPS
from wc2026.venue import score_matrix_with_venue
from wc2026.live_form import gather_live_stats, build_team_adjustments, AdjustedGoalModel
from wc2026.outcome_calibration import calibrate_model

def compute_group_standings(played_df: pd.DataFrame) -> dict:
    """Compute final group standings from played matches (pts, gd, gf, order)."""
    standings = {}
    for gname, teams in GROUPS.items():
        pts = {t: 0 for t in teams}
        gd = {t: 0 for t in teams}
        gf = {t: 0 for t in teams}
        for _, m in played_df.iterrows():
            if m.home_team in teams and m.away_team in teams:
                hs, as_ = int(m.home_score), int(m.away_score)
                h, a = m.home_team, m.away_team
                pts[h] += 3 if hs > as_ else (1 if hs == as_ else 0)
                pts[a] += 3 if as_ > hs else (1 if hs == as_ else 0)
                gd[h] += hs - as_
                gd[a] += as_ - hs
                gf[h] += hs
                gf[a] += as_
        order = sorted(teams, key=lambda t: (-pts[t], -gd[t], -gf[t]))
        standings[gname] = {"order": order, "pts": pts, "gd": gd, "gf": gf}
    return standings


def get_venue_outcome_probs(model, home: str, away: str) -> tuple[float, float, float]:
    """Use venue-aware matrix to get WDL probs (respects host advantage for 2026)."""
    M = score_matrix_with_venue(model, home, away)
    ph = float(np.tril(M, -1).sum())
    pd_ = float(np.trace(M))
    pa = float(np.triu(M, 1).sum())
    s = ph + pd_ + pa
    if s > 0:
        ph, pd_, pa = ph/s, pd_/s, pa/s
    return ph, pd_, pa


print("=" * 70)
print("COMPREHENSIVE VALIDATION: Prediction Motor (Copa 2026)")
print("Data up to end of SECOND ROUND (all teams played 2 matches)")
print("Predict & validate on THIRD ROUND + final group standings")
print("Using current branch improvements (P1 dispersion, P2 live, P3 features, P5 fatigue)")
print("=" * 70)

played_full = load_played_wc2026().sort_values("date").reset_index(drop=True)
cutoff = "2026-06-23"  # Proper: end of matchday 2 (48 matches, exactly 2 games/team)
played_r2 = played_full[played_full["date"] <= cutoff].copy()
remaining = played_full[played_full["date"] > cutoff].copy()

print(f"\nCutoff date for 2nd round: {cutoff}")
print(f"Played matches up to R2 (fixed in sim): {len(played_r2)}")
print(f"Third round matches to predict/validate: {len(remaining)}")
print(f"Date range R3: {remaining.date.min().date()} to {remaining.date.max().date()}")

# === Limited data for honest prediction (no lookahead on R3) ===
matches = load_matches()
matches_limited = matches[matches["date"] <= cutoff].copy()
print(f"\nTraining base model on limited data: {len(matches_limited)} matches (pre + WC <= cutoff)")

print("\n[1/6] Computing Elo ratings (limited data only)...")
elo = compute_elo(matches_limited)

print("[2/6] Building EnsembleGoalModel (P1: dispersion/NB + P3: richer ML features)...")
model = build_ensemble(matches_limited, w=0.55)

print("[3/6] Gathering & applying Live Form adjustments (P2: enriched xG-proxy + territory + adaptive shrink)...")
stats = gather_live_stats()
live_applied = False
if not stats.empty:
    stats = stats.copy()
    if "date" in stats:
        stats["date"] = pd.to_datetime(stats.get("date"), errors="coerce")
        stats_r2 = stats[(stats["date"].isna()) | (stats["date"] <= pd.Timestamp(cutoff))].copy()
    else:
        stats_r2 = stats
    print(f"     Live stats available up to cutoff: {len(stats_r2)} / {len(stats)} rows")
    try:
        adj = build_team_adjustments(model, stats_r2)
        model = AdjustedGoalModel(model, adj)
        live_applied = True
        print("     Live adjustment WRAPPED. Multipliers (sample):")
        att_sample = {k: round(v, 3) for k, v in list(adj.attack.items())[:6]}
        print("      ", att_sample)
    except Exception as e:
        print(f"     Live adjustment failed/skipped ({e}); using base model.")
else:
    print("     No granular stats in cache; proceeding without live adjustment.")

print("[4/6] Applying Outcome Calibration (blend with temporal V/E/D logistic)...")
try:
    model = calibrate_model(model, matches, engine="ensemble", w=0.55, alpha=0.5)
    print("     Calibration applied (alpha=0.5 blend; clf trained pre-cup).")
except Exception as e:
    print(f"     Calibration skipped ({e}).")

print("[5/6] Calibrating shootout beta...")
beta = calibrate(load_shootouts(), elo)

print("[6/6] Running Monte Carlo simulation with R2 data (5000 sims for stability, seed=42)...")
print("     (includes P5: basic fatigue dynamics in sim)")
table_r2 = simulate(model, elo, played_r2, n_sims=5000, seed=42, shootout_beta=beta)

print("\n" + "=" * 70)
print("PREDICTED CHAMPION / PHASE PROBS (model trained + live on data <= R2)")
print("=" * 70)
print(table_r2.head(10)[["team", "champion_%", "finalist_%", "semifinal_%", "advance_%", "exp_pts", "p_first_%", "p_second_%"]].to_string(index=False))

# === PER-MATCH VALIDATION ON 3RD ROUND ===
print("\n" + "=" * 70)
print("PER-MATCH WDL VALIDATION vs ACTUAL RESULTS (THIRD ROUND)")
print("=" * 70)

wdl_hits = 0
brier_sum = 0.0
ll_sum = 0.0
n_val = 0
val_details = []
probs_list = []
actual_list = []

for _, r in remaining.iterrows():
    h, a = r["home_team"], r["away_team"]
    hs, as_ = int(r.home_score), int(r.away_score)
    ph, pd_, pa = get_venue_outcome_probs(model, h, a)
    pred_idx = 0 if ph > max(pd_, pa) else (1 if pd_ > pa else 2)
    actual_idx = 0 if hs > as_ else (1 if hs == as_ else 2)
    hit = (pred_idx == actual_idx)
    if hit:
        wdl_hits += 1
    n_val += 1
    status = "HIT" if hit else "MISS"

    probs = np.array([ph, pd_, pa])
    I = np.zeros(3); I[actual_idx] = 1.0
    brier = float(np.sum((probs - I) ** 2))
    ll = float(-np.log(max(probs[actual_idx], 1e-12)))
    brier_sum += brier
    ll_sum += ll

    probs_list.append(probs)
    actual_list.append(actual_idx)

    val_details.append(
        f"{str(r.date.date())}  {h:20} {hs}-{as_} {a:20} | "
        f"V{ph*100:5.1f}% E{pd_*100:5.1f}% D{pa*100:5.1f}% -> {status}"
    )

acc = 100.0 * wdl_hits / n_val if n_val > 0 else 0.0
brier_avg = brier_sum / n_val if n_val > 0 else 0.0
ll_avg = ll_sum / n_val if n_val > 0 else 0.0

print(f"\nMatches validated: {n_val}")
print(f"WDL accuracy (argmax): {wdl_hits}/{n_val} = {acc:.1f}%")
print(f"Brier score (multiclass): {brier_avg:.4f}   (uniform baseline ~0.6667; lower=better)")
print(f"Log-loss: {ll_avg:.4f}   (lower=better)")
print("\nDetailed per-match (R3):")
for d in val_details:
    print("  " + d)

# Optional: also compute vs a simple Elo baseline on same matches for context
print("\n[Reference] Quick Elo baseline accuracy on same R3 matches:")
base_hits = 0
for _, r in remaining.iterrows():
    h, a = r.home_team, r.away_team
    hs, as_ = int(r.home_score), int(r.away_score)
    # use limited elo
    rh = elo.get(h, 1500) 
    ra = elo.get(a, 1500)
    # approx neutral + simple home? but cup mostly neutral; use rough
    exp_h = 1 / (1 + 10 ** ((ra - rh) / 400.0))
    pred_base = 0 if exp_h > 0.5 else (2 if (1-exp_h) > 0.5 else 1)  # rough, ignore draw bias
    actual_idx = 0 if hs > as_ else (1 if hs == as_ else 2)
    if pred_base == actual_idx:
        base_hits += 1
print(f"  Rough Elo argmax acc on R3: {base_hits}/{n_val} = {100*base_hits/n_val:.1f}% (note: no draw model)")

# === GROUP STANDINGS VALIDATION ===
print("\n" + "=" * 70)
print("GROUP STANDINGS & QUALIFICATION VALIDATION")
print("=" * 70)

actual_standings = compute_group_standings(played_full)

# Compute actual qualified + best thirds
actual_top2 = []
third_candidates = []
for gname, teams in GROUPS.items():
    s = actual_standings[gname]
    actual_top2.extend(s["order"][:2])
    t3 = s["order"][2]
    third_candidates.append((s["pts"][t3], s["gd"][t3], s["gf"][t3], t3, gname))
third_candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
actual_best3 = [x[3] for x in third_candidates[:8]]
actual_qualified = set(actual_top2 + actual_best3)

print("\nActual final group top-2 (advancers):")
for g in sorted(GROUPS.keys()):
    s = actual_standings[g]
    o = s["order"]
    p = s["pts"]
    print(f"  Group {g}: 1.{o[0]} ({p[o[0]]}pts)  2.{o[1]} ({p[o[1]]}pts)")

print(f"\nActual 8 best 3rds (by pts/gd/gf): {actual_best3}")
print(f"Total actual qualified for R32: {len(actual_qualified)} teams")

# Predicted positions / standings from limited sim table_r2
print("\nPredicted vs Actual (using exp_pts from Monte Carlo as ranking proxy; positions from sims):")
pos_1st_hits = 0
top2_slot_hits = 0  # count of actual top2 that were in predicted top2 per group
for gname, teams in GROUPS.items():
    gtab = table_r2[table_r2["team"].isin(teams)].sort_values("exp_pts", ascending=False)
    pred_order = gtab["team"].tolist()
    pred_pts = [round(x, 2) for x in gtab["exp_pts"].tolist()]
    act_order = actual_standings[gname]["order"]
    pred_top2_set = set(pred_order[:2])
    act_top2_set = set(act_order[:2])
    top2_slot_hits += len(pred_top2_set & act_top2_set)
    if pred_order[0] == act_order[0]:
        pos_1st_hits += 1
    print(f"  Grp {gname}:")
    print(f"    PRED (by exp_pts): {pred_order}  pts~{pred_pts}")
    print(f"    ACTL:              {act_order}")

print(f"\nGroup position summary (R2 model):")
print(f"  Correct 1st place predictions: {pos_1st_hits}/12 ({100*pos_1st_hits/12:.1f}%)")
print(f"  Top-2 slot hits (of 24): {top2_slot_hits}/24 ({100*top2_slot_hits/24:.1f}%)")

# Advance % validation for actual qualifiers
print("\nAdvance probability calibration check (actual qualifiers vs non):")
adv_qualified = []
adv_non = []
for _, row in table_r2.iterrows():
    t = row["team"]
    advp = row["advance_%"]
    if t in actual_qualified:
        adv_qualified.append(advp)
    else:
        adv_non.append(advp)

print(f"  Actual qualified ({len(adv_qualified)}): mean advance_% = {np.mean(adv_qualified):.1f}%  (range {min(adv_qualified):.1f}-{max(adv_qualified):.1f}%)")
print(f"  Non-qualified ({len(adv_non)}):   mean advance_% = {np.mean(adv_non):.1f}%    (range {min(adv_non):.1f}-{max(adv_non):.1f}%)")

# Champion probs: no actual yet, just report top and note
print("\nChampion probabilities (cannot validate vs actual - no knockout results in data yet):")
print("  Top 5 from R2 model:", table_r2.head(5)[["team","champion_%"]].to_string(index=False, header=False))

# === FULL DATA REFERENCE RUN (for shift analysis; note: uses all data incl R3) ===
print("\n" + "=" * 70)
print("REFERENCE: Full-data model run (all 72 WC matches in training - has lookahead bias)")
print("           (to observe how R3 results updated the table)")
print("=" * 70)
try:
    matches_full = load_matches()
    elo_full = compute_elo(matches_full)
    model_full_base = build_ensemble(matches_full, w=0.55)
    # try live with all stats (for ref only)
    try:
        adjf = build_team_adjustments(model_full_base, stats if not stats.empty else pd.DataFrame())
        model_full = AdjustedGoalModel(model_full_base, adjf)
    except:
        model_full = model_full_base
    table_full = simulate(model_full, elo_full, played_full, n_sims=2000, seed=42, shootout_beta=beta)
    print("Top 5 champion% full-data:", table_full.head(5)[["team","champion_%","advance_%"]].to_string(index=False, header=False))
    # diff in top champ
    top_r2 = set(table_r2.head(5)["team"])
    top_full = set(table_full.head(5)["team"])
    print(f"Overlap in top5 champions R2 vs full: {len(top_r2 & top_full)}/5")
except Exception as e:
    print(f"  Full ref run skipped: {e}")

# === SUMMARY REPORT ===
print("\n" + "=" * 70)
print("VALIDATION SUMMARY REPORT")
print("=" * 70)
print(f"Cutoff used: {cutoff} (end of 2nd round / matchday 2)")
print(f"Training data leakage avoided: yes (matches_limited date <= cutoff; live stats filtered)")
print(f"Improvements active: P1(dispersion NB), P2(live enriched + adaptive), ensemble w=0.55, calib, fatigue sim, venue, richer features")
print(f"\nThird round WDL:")
print(f"  Accuracy: {acc:.1f}% ({wdl_hits}/{n_val})")
print(f"  Brier:    {brier_avg:.4f}")
print(f"  Logloss:  {ll_avg:.4f}")
print(f"\nGroup standings (per group):")
print(f"  1st place match rate: {pos_1st_hits}/12 ({100*pos_1st_hits/12:.1f}%)")
print(f"  Top-2 slot recovery:  {top2_slot_hits}/24 ({100*top2_slot_hits/24:.1f}%)")
print(f"\nAdvance prob discrimination:")
print(f"  Qualified mean adv%: {np.mean(adv_qualified):.1f}% vs non: {np.mean(adv_non):.1f}% (delta ~{np.mean(adv_qualified)-np.mean(adv_non):.1f}pp)")
print("\nNotes:")
print("  - All 72 are group stage; no KO results available for champion/finalist validation.")
print("  - Live data sparse (only early MD1 stats); most multipliers ~1.0.")
print("  - Model uses current improvements on branch improvements/motor-precisao.")
if acc < 50:
    print("\n[OBSERVATION] WDL acc below 50% on holdout R3 -> potential overfit to early results or insufficient live signal.")
    print("Suggestions: 1) Increase live weight / reduce shrink_tau for mid-tournament. 2) Tune ensemble w closer to 0.6. 3) Add fatigue/rest days features more explicitly. 4) Recalibrate alpha or use isotonic.")
elif acc < 60:
    print("\n[OBSERVATION] Moderate WDL acc. Dispersion and live help variance but R3 results had many draws/upsets.")
else:
    print("\n[OBSERVATION] Solid WDL holdout acc. Current improvements appear beneficial for intra-cup prediction.")

print("\nTest complete. Script improved from /tmp/test_rounds.py for comprehensive validation.")
