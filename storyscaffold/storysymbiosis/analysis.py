#!/usr/bin/env python3
"""
analysis.py — StorySymbiosis session analysis and visualization.

Usage:
    python analysis.py                  # generates mock data + plots
    python analysis.py path/to/data/    # loads real JSON files from directory

Outputs a single figure: storysymbiosis_analysis.png
"""

import json
import os
import sys
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import seaborn as sns

# ── Constants ─────────────────────────────────────────────────────────────────

AGENTS = {
    "recombinability": {"name": "Remi", "color": "#7F77DD", "speak_prob": 0.60},
    "contrarian":      {"name": "Cass", "color": "#D85A30", "speak_prob": 0.50},
    "discoverability": {"name": "Dex",  "color": "#1D9E75", "speak_prob": 0.40},
    "reviewability":   {"name": "Rex",  "color": "#BA7517", "speak_prob": 0.35},
}

FEEDBACK_KEYS = ["explore", "different", "unsure"]
FEEDBACK_LABELS = {
    "explore":   "Worth exploring",
    "different": "Different direction",
    "unsure":    "Not sure",
}

PARTICIPANT_LABELS = ["P1", "P2", "P3", "P4", "P5"]


# ── Mock data generation ──────────────────────────────────────────────────────

def _ts(base: datetime, offset_s: float) -> str:
    return (base + timedelta(seconds=offset_s)).isoformat()


def generate_mock_session(participant_idx: int) -> dict:
    random.seed(participant_idx * 42)
    sid = str(uuid.uuid4())
    base = datetime(2026, 4, 15, 10, 0, 0, tzinfo=timezone.utc)
    audit = []
    states = []

    n_captures = random.randint(18, 35)
    t = 20  # 20s warmup

    # per-participant personality: some participants click more, some give harsher feedback
    click_rate    = random.uniform(0.45, 0.85)
    feedback_dist = [random.uniform(0.3, 0.6), random.uniform(0.2, 0.4), random.uniform(0.1, 0.25)]
    s = sum(feedback_dist); feedback_dist = [x / s for x in feedback_dist]

    for i in range(n_captures):
        # state update
        state_text = f"Participant {participant_idx+1} working on storyboard, scene {i+1}."
        states.append(state_text)
        audit.append({
            "ts": _ts(base, t), "event": "state_update", "agent": None,
            "state_index": i, "preview": state_text[:80], "ts_state": _ts(base, t),
        })

        # stochastic agent roll (cap at 1–2)
        winners = []
        for aid, info in AGENTS.items():
            if i < 1 and aid == "reviewability":
                continue
            effective = info["speak_prob"] * random.uniform(0.6, 1.0)
            if random.random() < effective:
                winners.append((aid, info["speak_prob"]))
        winners.sort(key=lambda x: x[1], reverse=True)
        cap = random.choices([1, 2], weights=[2, 1], k=1)[0]
        winners = winners[:cap]

        for aid, _ in winners:
            t += random.uniform(2, 8)
            trigger = "active" if random.random() < 0.15 else "passive"
            audit.append({
                "ts": _ts(base, t), "event": "hand_raised", "agent": aid,
                "state_index": i, "trigger": trigger,
            })

            # user may click
            if random.random() < click_rate:
                t += random.uniform(5, 30)
                audit.append({
                    "ts": _ts(base, t), "event": "comment_shown", "agent": aid,
                    "state_index": i, "trigger": "user_click",
                    "comment_preview": f"Sample comment from {AGENTS[aid]['name']}.",
                    "comment_full": f"Full comment from {AGENTS[aid]['name']} at state {i}.",
                })

                # artifact shown ~70% of the time after comment
                if random.random() < 0.70:
                    t += random.uniform(2, 6)
                    audit.append({
                        "ts": _ts(base, t), "event": "artifact_shown", "agent": aid,
                        "state_index": i, "artifact_title": f"Mock Artifact #{random.randint(1,99)}",
                        "artifact_creator": "Various", "artifact_year": str(random.randint(1960, 2024)),
                    })

                # feedback or dismiss
                if random.random() < 0.80:
                    t += random.uniform(5, 20)
                    fkey = random.choices(FEEDBACK_KEYS, weights=feedback_dist, k=1)[0]
                    audit.append({
                        "ts": _ts(base, t), "event": "comment_feedback", "agent": aid,
                        "state_index": i, "feedback_key": fkey,
                        "feedback_label": FEEDBACK_LABELS[fkey],
                        "comment_preview": f"Sample comment from {AGENTS[aid]['name']}.",
                    })
                else:
                    t += random.uniform(3, 10)
                    audit.append({
                        "ts": _ts(base, t), "event": "comment_dismissed", "agent": aid,
                        "state_index": i,
                    })

        t += 60  # next capture cycle

    return {"session_id": sid, "state_count": len(states), "states": states, "audit": audit}


def generate_mock_data(out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    for i, label in enumerate(PARTICIPANT_LABELS):
        data = generate_mock_session(i)
        path = out_dir / f"session_{label}.json"
        path.write_text(json.dumps(data, indent=2))
        print(f"  wrote {path}")


# ── Data loading ──────────────────────────────────────────────────────────────

def load_sessions(data_dir: Path) -> dict[str, list[dict]]:
    """Returns {participant_label: [audit_events]}"""
    files = sorted(data_dir.glob("*.json"))
    sessions = {}
    for i, f in enumerate(files):
        label = PARTICIPANT_LABELS[i] if i < len(PARTICIPANT_LABELS) else f"P{i+1}"
        data = json.loads(f.read_text())
        sessions[label] = data.get("audit", [])
    return sessions


def build_dataframe(sessions: dict[str, list[dict]]) -> pd.DataFrame:
    rows = []
    for participant, events in sessions.items():
        for e in events:
            rows.append({
                "participant":   participant,
                "event":         e.get("event", ""),
                "agent":         e.get("agent"),
                "trigger":       e.get("trigger", ""),
                "feedback_key":  e.get("feedback_key", ""),
                "artifact_title": e.get("artifact_title", ""),
                "state_index":   e.get("state_index"),
                "ts":            e.get("ts", ""),
            })
    return pd.DataFrame(rows)


# ── Plotting ──────────────────────────────────────────────────────────────────

DARK_BG   = "#0d0d1a"
CARD_BG   = "#13112a"
GRID_CLR  = "#1e1e3a"
TEXT_CLR  = "#c8c0d8"
ACCENT    = "#00ffe0"

AGENT_COLORS = {aid: info["color"] for aid, info in AGENTS.items()}
AGENT_NAMES  = {aid: info["name"]  for aid, info in AGENTS.items()}


def style_ax(ax, title=""):
    ax.set_facecolor(CARD_BG)
    ax.tick_params(colors=TEXT_CLR, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_CLR)
    ax.xaxis.label.set_color(TEXT_CLR)
    ax.yaxis.label.set_color(TEXT_CLR)
    ax.title.set_color(ACCENT)
    ax.set_title(title, fontsize=10, pad=8, fontweight="bold")
    ax.grid(axis="y", color=GRID_CLR, linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)


def plot_event_overview(ax, df):
    """Stacked bar: event types per participant."""
    event_types = ["hand_raised", "comment_shown", "artifact_shown",
                   "comment_feedback", "comment_dismissed"]
    colors = ["#7F77DD", "#1D9E75", "#BA7517", "#00ffe0", "#D85A30"]

    counts = (
        df[df["event"].isin(event_types)]
        .groupby(["participant", "event"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=event_types, fill_value=0)
    )

    bottom = np.zeros(len(counts))
    x = np.arange(len(counts))
    for evt, color in zip(event_types, colors):
        vals = counts[evt].values if evt in counts.columns else np.zeros(len(counts))
        ax.bar(x, vals, bottom=bottom, color=color, label=evt.replace("_", " "), width=0.55)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(counts.index, fontsize=9)
    ax.set_ylabel("Event count", fontsize=8)
    ax.legend(fontsize=7, loc="upper right",
              facecolor=DARK_BG, edgecolor=GRID_CLR, labelcolor=TEXT_CLR)
    style_ax(ax, "Event Overview per Participant")


def plot_feedback_stats(ax, df):
    """Grouped bar: feedback type distribution per participant."""
    fb = df[df["event"] == "comment_feedback"].copy()
    counts = (
        fb.groupby(["participant", "feedback_key"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=FEEDBACK_KEYS, fill_value=0)
    )

    x = np.arange(len(counts))
    width = 0.22
    offsets = [-width, 0, width]
    fb_colors = {"explore": "#00ffe0", "different": "#D85A30", "unsure": "#BA7517"}

    for i, key in enumerate(FEEDBACK_KEYS):
        vals = counts[key].values if key in counts.columns else np.zeros(len(counts))
        ax.bar(x + offsets[i], vals, width=width,
               color=fb_colors[key], label=FEEDBACK_LABELS[key], alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels(counts.index, fontsize=9)
    ax.set_ylabel("Count", fontsize=8)
    ax.legend(fontsize=7, facecolor=DARK_BG, edgecolor=GRID_CLR, labelcolor=TEXT_CLR)
    style_ax(ax, "Feedback Distribution per Participant")


def plot_artifact_initiations(ax, df):
    """Bar: artifact_shown events per participant, stacked by agent."""
    art = df[df["event"] == "artifact_shown"].copy()
    art = art[art["agent"].notna()]
    counts = (
        art.groupby(["participant", "agent"])
        .size()
        .unstack(fill_value=0)
    )

    x = np.arange(len(counts))
    bottom = np.zeros(len(counts))
    for aid in AGENTS:
        if aid not in counts.columns:
            continue
        vals = counts[aid].values
        ax.bar(x, vals, bottom=bottom,
               color=AGENT_COLORS[aid], label=AGENT_NAMES[aid], width=0.5)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(counts.index, fontsize=9)
    ax.set_ylabel("Artifact references surfaced", fontsize=8)
    ax.legend(fontsize=7, facecolor=DARK_BG, edgecolor=GRID_CLR, labelcolor=TEXT_CLR)
    style_ax(ax, "Artifact Initiations per Participant (by Agent)")


def plot_agent_feedback_crosstab(ax, df):
    """Heatmap: agent × feedback_key."""
    fb = df[df["event"] == "comment_feedback"].copy()
    fb = fb[fb["agent"].notna() & (fb["feedback_key"] != "")]

    ct = pd.crosstab(fb["agent"], fb["feedback_key"]).reindex(
        index=list(AGENTS.keys()),
        columns=FEEDBACK_KEYS,
        fill_value=0,
    )
    ct.index = [AGENT_NAMES.get(i, i) for i in ct.index]
    ct.columns = [FEEDBACK_LABELS[c] for c in ct.columns]

    sns.heatmap(
        ct, ax=ax, annot=True, fmt="d", cmap="RdPu",
        linewidths=0.5, linecolor=DARK_BG,
        cbar_kws={"shrink": 0.7},
        annot_kws={"size": 9, "color": "white"},
    )
    ax.set_xlabel("Feedback type", fontsize=8)
    ax.set_ylabel("Agent", fontsize=8)
    ax.tick_params(axis="x", rotation=15, labelsize=8)
    ax.tick_params(axis="y", rotation=0, labelsize=8)
    ax.tick_params(colors=TEXT_CLR)
    ax.xaxis.label.set_color(TEXT_CLR)
    ax.yaxis.label.set_color(TEXT_CLR)
    ax.title.set_color(ACCENT)
    ax.set_title("Agent × Feedback Type (cross-tab)", fontsize=10, pad=8, fontweight="bold")
    ax.set_facecolor(CARD_BG)
    ax.figure.axes[-1].tick_params(colors=TEXT_CLR, labelsize=7)


def plot_agent_click_crosstab(ax, df):
    """Heatmap: agent × participant click rate."""
    raised  = df[df["event"] == "hand_raised"].groupby(["participant", "agent"]).size()
    clicked = df[df["event"] == "comment_shown"].groupby(["participant", "agent"]).size()

    rate = (clicked / raised).fillna(0).unstack(level="agent").reindex(
        columns=list(AGENTS.keys()), fill_value=0
    )
    rate.columns = [AGENT_NAMES[c] for c in rate.columns]

    sns.heatmap(
        rate, ax=ax, annot=True, fmt=".0%", cmap="BuPu",
        linewidths=0.5, linecolor=DARK_BG,
        vmin=0, vmax=1,
        cbar_kws={"shrink": 0.7, "format": "%.0%%"},
        annot_kws={"size": 9, "color": "white"},
    )
    ax.set_xlabel("Agent", fontsize=8)
    ax.set_ylabel("Participant", fontsize=8)
    ax.tick_params(axis="x", rotation=15, labelsize=8)
    ax.tick_params(axis="y", rotation=0, labelsize=8)
    ax.tick_params(colors=TEXT_CLR)
    ax.xaxis.label.set_color(TEXT_CLR)
    ax.yaxis.label.set_color(TEXT_CLR)
    ax.title.set_color(ACCENT)
    ax.set_title("Click-through Rate: Agent × Participant (cross-tab)", fontsize=10, pad=8, fontweight="bold")
    ax.set_facecolor(CARD_BG)
    ax.figure.axes[-1].tick_params(colors=TEXT_CLR, labelsize=7)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("mock_data")

    if not any(data_dir.glob("*.json")):
        print(f"No JSON files found in {data_dir} — generating mock data...")
        generate_mock_data(data_dir)

    print(f"Loading sessions from {data_dir}...")
    sessions = load_sessions(data_dir)
    df = build_dataframe(sessions)
    print(f"  {len(df)} total events across {len(sessions)} participants")

    # ── Figure layout ──────────────────────────────────────────────────────────
    plt.rcParams.update({
        "figure.facecolor":  DARK_BG,
        "axes.facecolor":    CARD_BG,
        "text.color":        TEXT_CLR,
        "font.family":       "monospace",
        "font.size":         9,
    })

    fig = plt.figure(figsize=(18, 14))
    fig.suptitle(
        "StorySymbiosis — Session Analysis",
        fontsize=15, fontweight="bold", color=ACCENT, y=0.98,
    )

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)
    ax1 = fig.add_subplot(gs[0, :2])   # event overview — wide
    ax2 = fig.add_subplot(gs[0, 2])    # artifact initiations
    ax3 = fig.add_subplot(gs[1, :2])   # feedback stats — wide
    ax4 = fig.add_subplot(gs[1, 2])    # (unused — reserved)

    # Replace ax4 with two heatmaps side by side in the bottom row
    fig.delaxes(ax3)
    fig.delaxes(ax4)
    gs_bot = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[1, :], wspace=0.45)
    ax3 = fig.add_subplot(gs_bot[0])
    ax4 = fig.add_subplot(gs_bot[1])

    plot_event_overview(ax1, df)
    plot_artifact_initiations(ax2, df)
    plot_feedback_stats(ax3, df)
    plot_agent_feedback_crosstab(ax4, df)

    # Fifth plot: click-through cross-tab — add as inset row
    fig2, ax5 = plt.subplots(figsize=(7, 4), facecolor=DARK_BG)
    plot_agent_click_crosstab(ax5, df)
    fig2.tight_layout()
    out2 = "storysymbiosis_clickthrough.png"
    fig2.savefig(out2, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"  saved {out2}")

    out = "storysymbiosis_analysis.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"  saved {out}")
    plt.show()


if __name__ == "__main__":
    main()
