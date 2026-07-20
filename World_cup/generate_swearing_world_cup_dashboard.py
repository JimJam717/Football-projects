import argparse
import json
from pathlib import Path

from swearing_pipeline import LEADERBOARD_DIR, MATCH_CONFIG_PATH, SCORED_DIR, load_json
from swearing_tournament import (
    MATCH_METRICS_OUTPUT_PATH,
    POPULATION_PATH,
    TOURNAMENT_OUTPUT_PATH,
    build_tournament_data,
)


DEFAULT_OUTPUT_PATH = Path("worldcup_discourse/swearing_world_cup_dashboard.html")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the animated Swearing World Cup dashboard.")
    parser.add_argument("--match-config", default=MATCH_CONFIG_PATH)
    parser.add_argument("--leaderboard", default=LEADERBOARD_DIR / "swearing_leaderboard.json")
    parser.add_argument("--scored-dir", default=SCORED_DIR)
    parser.add_argument("--population", default=POPULATION_PATH)
    parser.add_argument("--tournament-output", default=TOURNAMENT_OUTPUT_PATH)
    parser.add_argument("--match-output", default=MATCH_METRICS_OUTPUT_PATH)
    parser.add_argument("--html-output", default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Animated Swearing World Cup</title>
  <style>
    @import url("https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,600;0,700;0,800;0,900;1,800&family=IBM+Plex+Mono:wght@400;500;600&family=Space+Grotesk:wght@400;500;600;700&display=swap");

    :root {
      color-scheme: light;
      --pitch-haze: #C7D7B1;
      --ink: #17231E;
      --paper: #F2F0E8;
      --signal-blue: #1E5AA8;
      --card-yellow: #F4C542;
      --card-red: #D93632;
      --line: 3px solid var(--ink);
      --shadow: 6px 6px 0 var(--ink);
      --shadow-sm: 3px 3px 0 var(--ink);
    }

    * { box-sizing: border-box; }

    html {
      background: var(--pitch-haze);
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(rgba(23, 35, 30, 0.055) 3px, transparent 3px),
        linear-gradient(90deg, rgba(23, 35, 30, 0.055) 3px, transparent 3px),
        var(--pitch-haze);
      background-size: 28px 28px;
      color: var(--ink);
      font-family: "Space Grotesk", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      z-index: 1000;
      pointer-events: none;
      background: repeating-linear-gradient(
        0deg,
        rgba(23, 35, 30, 0.09) 0,
        rgba(23, 35, 30, 0.09) 1px,
        transparent 1px,
        transparent 5px
      );
      mix-blend-mode: multiply;
      opacity: 0.22;
    }

    main {
      width: min(1440px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 42px;
    }

    h1, h2, h3, p { margin: 0; }

    h1 {
      font-size: clamp(30px, 4vw, 56px);
      line-height: 0.92;
      font-family: "Barlow Condensed", ui-sans-serif, sans-serif;
      font-weight: 900;
      text-transform: uppercase;
      color: var(--ink);
      text-shadow: 4px 4px 0 var(--card-red);
      max-width: 960px;
    }

    h2 {
      font-family: "Barlow Condensed", ui-sans-serif, sans-serif;
      font-size: 24px;
      line-height: 0.95;
      font-weight: 800;
      text-transform: uppercase;
    }

    h3 {
      color: var(--ink);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    button, select {
      border: var(--line);
      background: var(--ink);
      color: var(--paper);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 14px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      min-height: 40px;
      box-shadow: 3px 3px 0 var(--signal-blue);
    }

    button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 9px 12px;
      cursor: pointer;
    }

    button:hover {
      background: var(--signal-blue);
    }

    button:active {
      transform: translate(3px, 3px);
      box-shadow: none;
    }

    button[aria-pressed="true"], button.active {
      background: var(--card-yellow);
      color: var(--ink);
    }

    select {
      padding: 9px 32px 9px 12px;
      background:
        linear-gradient(45deg, transparent 50%, var(--paper) 50%) calc(100% - 18px) 17px / 7px 7px no-repeat,
        linear-gradient(135deg, var(--paper) 50%, transparent 50%) calc(100% - 12px) 17px / 7px 7px no-repeat,
        var(--ink);
      appearance: none;
    }

    .hero {
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 420px);
      gap: 22px;
      align-items: stretch;
      padding: 20px;
      border: var(--line);
      background: var(--paper);
      box-shadow: var(--shadow);
    }

    .hero::before,
    #ticker::before {
      content: "LIVE";
      position: absolute;
      top: -3px;
      left: -3px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 7px 11px;
      background: var(--card-red);
      color: var(--paper);
      border: var(--line);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .hero::after,
    #ticker .brand::before {
      content: "";
      position: absolute;
      top: 8px;
      left: 53px;
      width: 8px;
      height: 8px;
      background: var(--paper);
      animation: livePulse 1.25s steps(2, end) infinite;
    }

    .lede {
      margin-top: 16px;
      color: var(--ink);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 16px;
      line-height: 1.55;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      max-width: 920px;
    }

    .champion-card {
      position: relative;
      border: var(--line);
      background: var(--card-red);
      box-shadow: var(--shadow-sm);
      padding: 18px;
      color: var(--paper);
      overflow: hidden;
    }

    .champion-card::after,
    .champ-inner::after {
      content: "";
      position: absolute;
      inset: 12px;
      border: 2px dashed var(--ink);
      pointer-events: none;
    }

    .champion-name {
      margin-top: 6px;
      font-family: "Barlow Condensed", ui-sans-serif, sans-serif;
      font-size: clamp(42px, 6vw, 84px);
      line-height: 0.86;
      font-weight: 900;
      text-transform: uppercase;
      color: var(--paper);
      text-shadow: 4px 4px 0 var(--ink);
    }

    .champion-meta {
      margin-top: 8px;
      display: inline-block;
      background: var(--card-yellow);
      color: var(--ink);
      border: var(--line);
      padding: 6px 8px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 13px;
      line-height: 1.45;
      font-weight: 600;
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin: 20px 0;
    }

    .step-status {
      border: var(--line);
      background: var(--card-yellow);
      color: var(--ink);
      padding: 8px 10px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      box-shadow: var(--shadow-sm);
    }

    .dashboard {
      display: grid;
      grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
      gap: 22px;
      align-items: start;
    }

    section, .panel {
      border: var(--line);
      background: var(--paper);
      box-shadow: var(--shadow);
      padding: 18px;
    }

    .groups {
      display: grid;
      gap: 12px;
    }

    .group-card {
      background: var(--paper);
      border: var(--line);
      box-shadow: var(--shadow-sm);
      padding: 12px;
      opacity: 0.36;
      transform: translateY(4px) rotate(0.8deg);
      transition: opacity 280ms ease, transform 280ms ease, border-color 280ms ease;
    }

    .group-card.visible {
      opacity: 1;
      transform: translateY(0) rotate(0deg);
    }

    .group-head, .team-row, .match-row, .award-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .team-list {
      display: grid;
      gap: 7px;
      margin-top: 10px;
    }

    .team-row {
      position: relative;
      min-height: 34px;
      padding: 7px 8px;
      border: 2px solid var(--ink);
      background: rgba(242, 240, 232, 0.62);
    }

    .team-name {
      min-width: 0;
      font-weight: 700;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .team-code {
      color: var(--signal-blue);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
    }

    .metric {
      flex: 0 0 auto;
      color: var(--card-red);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-weight: 600;
      font-size: 13px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 22px;
      height: 22px;
      border: 2px solid var(--ink);
      background: var(--paper);
      color: var(--ink);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      font-weight: 600;
    }

    .badge.gold { background: var(--card-yellow); color: var(--ink); }
    .badge.warn { background: var(--card-red); color: var(--paper); }
    .badge.ok { background: var(--signal-blue); color: var(--paper); }

    .stage-grid {
      display: grid;
      gap: 18px;
    }

    .third-table {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }

    .third-table .team-row {
      opacity: 0.45;
      filter: grayscale(1);
    }

    .third-table .team-row.qualified-third {
      opacity: 1;
      filter: none;
      background: var(--card-yellow);
      border: var(--line);
      box-shadow: var(--shadow-sm);
      padding-top: 22px;
    }

    .third-table .team-row.qualified-third::after {
      content: "ADVANCES";
      position: absolute;
      top: -3px;
      right: -3px;
      padding: 3px 6px;
      border: 2px solid var(--ink);
      background: var(--signal-blue);
      color: var(--paper);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.06em;
    }

    .bracket {
      display: grid;
      grid-template-columns: repeat(5, minmax(180px, 1fr));
      gap: 12px;
      overflow-x: auto;
      padding-bottom: 2px;
    }

    .round-column {
      min-width: 180px;
      display: grid;
      gap: 10px;
      align-content: start;
      opacity: 0.24;
      transition: opacity 280ms ease;
    }

    .round-column.visible { opacity: 1; }

    .round-title {
      display: inline-block;
      width: fit-content;
      background: var(--ink);
      color: var(--paper);
      border: var(--line);
      padding: 5px 8px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .match-card {
      border: var(--line);
      background: var(--paper);
      box-shadow: var(--shadow-sm);
      padding: 10px;
    }

    .match-card.champion-path {
      background:
        repeating-linear-gradient(
          -45deg,
          rgba(244, 197, 66, 0.28) 0,
          rgba(244, 197, 66, 0.28) 8px,
          transparent 8px,
          transparent 17px
        ),
        var(--paper);
    }

    .match-slot {
      color: var(--signal-blue);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      margin-bottom: 7px;
    }

    .match-row {
      min-height: 30px;
      padding: 5px 6px;
      border-left: 6px solid transparent;
    }

    .match-row.winner {
      background: var(--card-yellow);
      color: var(--ink);
      border-left-color: var(--card-red);
    }

    .match-warn {
      margin-top: 7px;
      border: 2px solid var(--card-red);
      background: var(--paper);
      color: var(--card-red);
      padding: 5px 6px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      line-height: 1.35;
    }

    .awards {
      display: none;
    }

    .awards.visible {
      display: grid;
      gap: 14px;
    }

    .award-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .award-spotlight {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(220px, 340px);
      gap: 14px;
      align-items: stretch;
    }

    .award-main {
      background: var(--paper);
      border: var(--line);
      box-shadow: var(--shadow-sm);
      padding: 18px;
    }

    .award-title {
      display: inline-block;
      color: var(--paper);
      background: var(--card-red);
      border: var(--line);
      padding: 6px 10px;
      font-family: "Barlow Condensed", ui-sans-serif, sans-serif;
      font-size: 42px;
      line-height: 0.9;
      font-weight: 900;
      text-transform: uppercase;
      text-shadow: 3px 3px 0 var(--ink);
      margin-top: 6px;
    }

    .award-note {
      color: var(--ink);
      margin-top: 12px;
      line-height: 1.45;
      font-size: 14px;
    }

    .mini-stats {
      display: grid;
      gap: 10px;
    }

    .mini-stat {
      background: var(--card-yellow);
      border: var(--line);
      box-shadow: var(--shadow-sm);
      padding: 12px;
    }

    .mini-label {
      color: var(--ink);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .mini-value {
      margin-top: 4px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 21px;
      font-weight: 600;
    }

    .method {
      margin-top: 22px;
      color: var(--ink);
      font-size: 13px;
      line-height: 1.5;
    }

    #stage {
      background:
        linear-gradient(rgba(23, 35, 30, 0.055) 3px, transparent 3px),
        linear-gradient(90deg, rgba(23, 35, 30, 0.055) 3px, transparent 3px),
        var(--pitch-haze);
      background-size: 28px 28px;
    }

    #ticker {
      position: relative;
      background: var(--ink);
      color: var(--paper);
      border: var(--line);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    #phaseLabel {
      background: var(--card-yellow);
      color: var(--ink);
      border: 2px solid var(--ink);
      padding: 4px 8px;
    }

    #phase-intro h1 {
      color: var(--ink);
      text-shadow: 4px 4px 0 var(--card-red);
      -webkit-text-fill-color: currentColor;
      background: none;
    }

    #phase-intro p {
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .team-card {
      background: var(--paper);
      border: var(--line);
      box-shadow: var(--shadow-sm);
      transform: translateY(4px) rotate(0.8deg);
    }

    .team-card.visible {
      transform: translateY(0) rotate(0deg);
    }

    .meter-track {
      border: var(--line);
      background:
        repeating-linear-gradient(
          -45deg,
          rgba(23, 35, 30, 0.14) 0,
          rgba(23, 35, 30, 0.14) 8px,
          rgba(242, 240, 232, 0.4) 8px,
          rgba(242, 240, 232, 0.4) 16px
        );
    }

    .meter-fill {
      background: var(--signal-blue);
    }

    .meter-fill--low { background: var(--signal-blue); }
    .meter-fill--mid { background: var(--card-yellow); }
    .meter-fill--high { background: var(--card-red); }

    .third-slot.picked {
      position: relative;
      background: var(--card-yellow);
      border: var(--line);
      box-shadow: var(--shadow-sm);
    }

    .third-slot.picked::after {
      content: "ADVANCES";
      position: absolute;
      top: -3px;
      right: -3px;
      background: var(--signal-blue);
      color: var(--paper);
      border: 2px solid var(--ink);
      padding: 3px 6px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 10px;
      font-weight: 600;
    }

    .matchup {
      border: var(--line);
      box-shadow: var(--shadow-sm);
      background: var(--paper);
    }

    .m-team.winner {
      background: var(--card-yellow);
      color: var(--ink);
      border-left: 6px solid var(--card-red);
    }

    .champ-inner {
      position: relative;
      border: var(--line);
      box-shadow: var(--shadow);
      background: var(--paper);
    }

    #phase-champion h1 {
      display: inline-block;
      background: var(--card-red);
      color: var(--paper);
      border: var(--line);
      padding: 8px 12px;
    }

    #championCode {
      font-family: "Barlow Condensed", ui-sans-serif, sans-serif;
      color: var(--paper);
      text-shadow: 4px 4px 0 var(--ink);
    }

    #championStat {
      background: var(--card-yellow);
      color: var(--ink);
      border: var(--line);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
    }

    #controls button {
      background: var(--ink);
      color: var(--paper);
      border: var(--line);
      box-shadow: 3px 3px 0 var(--signal-blue);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      text-transform: uppercase;
    }

    .dots .dot {
      width: 17px;
      height: 8px;
      border: 2px solid var(--ink);
      background: var(--paper);
    }

    .dots .dot.on,
    .dots .dot.active {
      width: 42px;
      background:
        repeating-linear-gradient(
          -45deg,
          var(--card-red) 0,
          var(--card-red) 7px,
          var(--card-yellow) 7px,
          var(--card-yellow) 14px
        );
      animation: hazardPulse 1.25s steps(2, end) infinite;
    }

    body {
      height: 100vh;
      overflow: hidden;
    }

    main {
      width: min(1440px, calc(100vw - 24px));
      height: 100vh;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 12px;
      padding: 12px 0;
    }

    #ticker {
      min-height: 48px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 8px 12px 8px 78px;
      box-shadow: var(--shadow-sm);
    }

    #ticker .brand {
      font-weight: 600;
    }

    #stage {
      position: relative;
      min-height: 0;
      height: 100%;
      overflow: hidden;
      border: var(--line);
      box-shadow: var(--shadow);
    }

    .phase {
      position: absolute;
      inset: 0;
      opacity: 0;
      pointer-events: none;
      transform: translateY(14px) scale(0.985);
      transition: opacity 360ms ease, transform 360ms ease;
      padding: 18px;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 14px;
      overflow: hidden;
    }

    .phase.active {
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0) scale(1);
    }

    .phase.active .phase-head,
    .phase.active .intro-copy,
    .phase.active .champ-inner {
      animation: phaseStamp 420ms cubic-bezier(.2, .85, .2, 1) both;
    }

    .phase-head {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      min-width: 0;
    }

    .phase-kicker {
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .phase-panel {
      min-height: 0;
      display: grid;
      align-content: center;
      overflow: hidden;
    }

    #phase-intro {
      grid-template-columns: minmax(0, 1fr);
      place-items: center stretch;
    }

    .intro-copy {
      max-width: 1040px;
      border: var(--line);
      background: var(--paper);
      box-shadow: var(--shadow);
      padding: clamp(18px, 4vw, 44px);
    }

    .intro-copy h1 {
      font-size: clamp(54px, 10vw, 150px);
    }

    #teamGrid.groups {
      grid-template-columns: 1fr;
      align-content: center;
      max-width: 860px;
      width: min(100%, 860px);
      justify-self: center;
    }

    .team-card {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(220px, 0.8fr);
      align-items: center;
      gap: 10px;
      padding: 12px;
      opacity: 0;
      transform: translateY(22px) rotate(1.2deg);
      animation: cardStamp 520ms cubic-bezier(.2, .85, .2, 1) forwards;
      animation-delay: var(--delay, 0ms);
    }

    .team-card-head {
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 10px;
    }

    .team-card-name {
      min-width: 0;
      font-weight: 700;
      font-size: clamp(18px, 2vw, 27px);
      line-height: 1;
      text-transform: uppercase;
    }

    .team-card-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
    }

    .meter-track {
      height: 18px;
      overflow: hidden;
    }

    .meter-fill {
      height: 100%;
      transition: width 360ms ease;
    }

    #thirdGrid .team-row {
      opacity: 0;
      transform: translateY(18px) rotate(0.8deg);
      animation: cardStamp 420ms cubic-bezier(.2, .85, .2, 1) forwards;
      animation-delay: var(--delay, 0ms);
    }

    #thirdGrid.third-table {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      align-content: center;
    }

    #bracketRounds.bracket {
      overflow: hidden;
      grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
      align-content: center;
      gap: 8px;
    }

    #phase-bracket .match-card {
      padding: 7px;
      opacity: 0;
      transform: translateY(18px) scale(0.98);
      animation: matchSlam 460ms cubic-bezier(.2, .85, .2, 1) forwards;
      animation-delay: var(--delay, 0ms);
    }

    #phase-bracket .match-row {
      min-height: 24px;
      padding: 3px 5px;
      gap: 6px;
    }

    #phase-bracket .team-name {
      font-size: 12px;
    }

    #phase-bracket .metric {
      font-size: 11px;
    }

    #phase-champion {
      grid-template-rows: minmax(0, 1fr);
    }

    .champ-inner {
      display: grid;
      grid-template-columns: minmax(260px, 0.85fr) minmax(320px, 1.15fr);
      gap: clamp(12px, 2vw, 24px);
      align-items: stretch;
      padding: clamp(14px, 2vw, 26px);
      overflow: hidden;
    }

    .champ-title-block {
      min-width: 0;
    }

    #championCode {
      font-size: clamp(58px, 9vw, 132px);
      line-height: 0.82;
      font-weight: 900;
      background: var(--card-red);
      border: var(--line);
      padding: 10px 12px;
      width: 100%;
      max-width: 100%;
      overflow-wrap: anywhere;
    }

    #championStat {
      display: inline-block;
      margin-top: 14px;
      padding: 8px 10px;
      font-size: 14px;
      font-weight: 600;
      text-transform: uppercase;
    }

    #phase-champion.active #championCode {
      animation: championHit 620ms steps(3, end) both;
    }

    #awardsRoot.awards {
      display: grid;
      gap: 10px;
      min-width: 0;
      align-content: start;
      overflow: hidden;
    }

    #awardsRoot .award-buttons {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      max-height: none;
      overflow: visible;
    }

    #awardsRoot .award-buttons button {
      min-width: 0;
      width: 100%;
      padding: 8px 9px;
      font-size: 12px;
      white-space: normal;
      line-height: 1.15;
    }

    #awardsRoot .award-spotlight {
      grid-template-columns: 1fr;
      gap: 10px;
    }

    #awardsRoot .award-main {
      padding: 12px;
    }

    #awardsRoot .award-note {
      max-height: 68px;
      overflow: hidden;
    }

    #awardsRoot .award-title {
      font-size: clamp(28px, 4vw, 48px);
      max-width: 100%;
      overflow-wrap: anywhere;
    }

    #awardsRoot .mini-stats {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    #controls {
      margin: 0;
      min-height: 58px;
      border: var(--line);
      background: var(--paper);
      box-shadow: var(--shadow-sm);
      padding: 8px;
    }

    #dots {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      min-width: 120px;
    }

    .dot {
      display: inline-block;
      padding: 0;
      min-width: 0;
      min-height: 0;
      box-shadow: none;
      font-size: 0;
    }

    @keyframes livePulse {
      0%, 45% { opacity: 1; filter: brightness(1.25); }
      46%, 100% { opacity: 0.35; filter: brightness(0.8); }
    }

    @keyframes hazardPulse {
      0%, 45% { filter: brightness(1.08); }
      46%, 100% { filter: brightness(0.78); }
    }

    @keyframes phaseStamp {
      0% { opacity: 0; transform: translateY(18px) scale(0.985); }
      72% { opacity: 1; transform: translateY(-2px) scale(1.01); }
      100% { opacity: 1; transform: translateY(0) scale(1); }
    }

    @keyframes cardStamp {
      0% { opacity: 0; transform: translateY(22px) rotate(1.2deg); }
      70% { opacity: 1; transform: translateY(-3px) rotate(-0.35deg); }
      100% { opacity: 1; transform: translateY(0) rotate(0deg); }
    }

    @keyframes matchSlam {
      0% { opacity: 0; transform: translateY(18px) scale(0.98); }
      65% { opacity: 1; transform: translateY(-2px) scale(1.015); }
      100% { opacity: 1; transform: translateY(0) scale(1); }
    }

    @keyframes championHit {
      0% { opacity: 0; transform: translateX(-12px); filter: brightness(0.7); }
      35% { opacity: 1; transform: translateX(8px); filter: brightness(1.45); }
      65% { transform: translateX(-4px); filter: brightness(0.9); }
      100% { opacity: 1; transform: translateX(0); filter: brightness(1); }
    }

    @media (max-width: 980px) {
      main { width: min(100vw - 20px, 760px); }
      .hero, .dashboard, .award-spotlight, .champ-inner { grid-template-columns: 1fr; }
      .bracket { grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); }
      #teamGrid.groups { grid-template-columns: 1fr; }
      #thirdGrid.third-table { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .team-card { grid-template-columns: 1fr; }
      .phase { padding: 12px; }
    }

    @media (max-width: 520px) {
      main { width: calc(100vw - 12px); padding: 8px 0; gap: 8px; }
      .hero { gap: 14px; }
      .controls { align-items: stretch; }
      .controls button, .controls select { flex: 1 1 130px; }
      section, .panel, .champion-card { padding: 12px; }
      .team-name { white-space: normal; }
      .metric { font-size: 12px; }
      .award-title { font-size: 34px; }
      .hero::before { position: static; width: fit-content; margin-bottom: 10px; }
      .hero::after { display: none; }
      #ticker { padding-left: 70px; font-size: 11px; }
      .phase-head { align-items: start; flex-direction: column; gap: 8px; }
      #teamGrid.groups { grid-template-columns: 1fr; }
      #thirdGrid.third-table { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
      #bracketRounds.bracket { grid-template-columns: 1fr; gap: 5px; }
      #phase-bracket .match-card { padding: 5px; }
      #phase-bracket .match-slot { margin-bottom: 3px; font-size: 10px; }
      #championCode { font-size: clamp(48px, 17vw, 82px); }
      #awardsRoot .award-buttons { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      #awardsRoot .award-title { font-size: 28px; }
      #controls { min-height: 96px; }
      #dots { flex: 1 1 100%; }
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        animation-duration: 1ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 1ms !important;
        scroll-behavior: auto !important;
      }
    }
  </style>
</head>
<body>
  <main>
    <div id="ticker">
      <span class="brand">Swearing World Cup</span>
      <span id="phaseLabel">Intro</span>
    </div>

    <div id="stage" aria-live="polite">
      <section class="phase active" id="phase-intro" data-phase="intro">
        <div class="intro-copy">
          <div class="phase-kicker">Broadcast disciplinary desk</div>
          <h1>Swearing World Cup</h1>
          <p class="lede">A FIFA-style replay where subreddit-identity fanbases advance by profanity density. Qualified samples beat low-sample teams before rate tiebreakers are applied.</p>
        </div>
      </section>

      <section class="phase" id="phase-groups" data-phase="groups">
        <div class="phase-head">
          <div>
            <div class="phase-kicker">Group Reveal</div>
            <h2>Group <span id="groupLetter">A</span></h2>
          </div>
          <span class="badge ok">4 Teams</span>
        </div>
        <div class="phase-panel">
          <div class="groups" id="teamGrid"></div>
        </div>
      </section>

      <section class="phase" id="phase-third" data-phase="third">
        <div class="phase-head">
          <div>
            <div class="phase-kicker">Best Thirds</div>
            <h2 id="thirdTitle">Third-place table</h2>
          </div>
          <span class="badge gold" id="thirdKey"></span>
        </div>
        <div class="phase-panel">
          <div class="third-table" id="thirdGrid"></div>
        </div>
      </section>

      <section class="phase" id="phase-bracket" data-phase="bracket">
        <div class="phase-head">
          <div>
            <div class="phase-kicker">Knockout</div>
            <h2 id="roundTitle">Round of 32</h2>
          </div>
          <span class="badge gold" id="liveRound">Round of 32</span>
        </div>
        <div class="phase-panel">
          <div class="bracket" id="bracketRounds"></div>
        </div>
      </section>

      <section class="phase" id="phase-champion" data-phase="champion">
        <div class="champ-inner">
          <div class="champ-title-block">
            <div class="phase-kicker">Final incident report</div>
            <h1>Champion</h1>
            <div id="championCode">LOCKED</div>
            <div id="championStat">Play through the bracket to reveal the winner.</div>
          </div>

          <section class="awards" id="awardsRoot">
            <div class="award-head">
              <div>
                <div class="phase-kicker">Awards</div>
                <h2>Spotlight winners</h2>
              </div>
            </div>
            <div class="award-buttons" id="awardButtons"></div>
            <div class="award-spotlight">
              <div class="award-main">
                <h3 id="awardLabel"></h3>
                <div class="award-title" id="awardWinner"></div>
                <p class="award-note" id="awardNote"></p>
              </div>
              <div class="mini-stats">
                <div class="mini-stat">
                  <div class="mini-label">Metric</div>
                  <div class="mini-value" id="awardMetric"></div>
                </div>
                <div class="mini-stat">
                  <div class="mini-label">Value</div>
                  <div class="mini-value" id="awardValue"></div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </section>
    </div>

    <div class="controls" id="controls" aria-label="Playback controls">
      <button type="button" id="prevBtn">Previous</button>
      <button type="button" id="playBtn" aria-pressed="false">Play</button>
      <button type="button" id="nextBtn">Next</button>
      <select id="phaseSelect" aria-label="Jump to phase"></select>
      <div class="dots" id="dots" aria-label="Step progress"></div>
      <div class="step-status" id="stepStatus"></div>
    </div>
  </main>

  <script>
    const tournament = __DATA__;

    const steps = [
      { phase: "intro", label: "Intro" },
      ...tournament.groups.map((group, groupIndex) => ({
        phase: "groups",
        label: `Group ${group.group}`,
        groupIndex
      })),
      { phase: "third", label: "Third-place table", qualified: false },
      { phase: "third", label: "Best eight thirds", qualified: true },
      ...tournament.bracket.map((round, roundIndex) => ({
        phase: "bracket",
        label: round.round,
        roundIndex
      })),
      { phase: "champion", label: "Champion + awards" }
    ];

    let stepIndex = 0;
    let timer = null;
    const availableAwards = tournament.awards.filter(award => award.winner && award.value !== null && award.value !== undefined);
    let activeAward = availableAwards[0]?.id;

    const phases = Array.from(document.querySelectorAll(".phase"));
    const teamGrid = document.getElementById("teamGrid");
    const thirdGrid = document.getElementById("thirdGrid");
    const bracketRounds = document.getElementById("bracketRounds");
    const phaseSelect = document.getElementById("phaseSelect");
    const stepStatus = document.getElementById("stepStatus");
    const phaseLabel = document.getElementById("phaseLabel");
    const groupLetter = document.getElementById("groupLetter");
    const thirdTitle = document.getElementById("thirdTitle");
    const roundTitle = document.getElementById("roundTitle");
    const liveRound = document.getElementById("liveRound");
    const dots = document.getElementById("dots");
    const awardButtons = document.getElementById("awardButtons");

    function formatMetric(value, digits = 2) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
      return Number(value).toFixed(digits).replace(/0+$/, "").replace(/\.$/, "");
    }

    function teamLabel(team) {
      if (!team) return "n/a";
      return team.country || team.word || team.match_id || "n/a";
    }

    function statusBadge(team) {
      if (team.data_status === "qualified") return '<span class="badge ok">Q</span>';
      if (team.data_status === "low_sample") return '<span class="badge warn">L</span>';
      return '<span class="badge warn">M</span>';
    }

    function meterClass(value) {
      const numeric = Number(value) || 0;
      if (numeric >= 75) return "meter-fill--high";
      if (numeric >= 50) return "meter-fill--mid";
      return "meter-fill--low";
    }

    function renderTeamRow(team, options = {}) {
      const thirdClass = options.thirdQualified ? " qualified-third" : "";
      return `
        <div class="team-row${thirdClass}">
          <span class="badge${options.position <= 2 ? " gold" : ""}">${options.position || team.group_position || ""}</span>
          <div class="team-name">${team.country}<span class="team-code"> ${team.code || ""}</span></div>
          ${statusBadge(team)}
          <div class="metric">${formatMetric(team.swears_per_1000_words)} / 1k</div>
        </div>
      `;
    }

    function renderTeamCard(team, position) {
      const metric = Number(team.swears_per_1000_words) || 0;
      const width = Math.max(2, Math.min(100, metric));
      return `
        <article class="team-card" style="--delay: ${(position - 1) * 110}ms">
          <div class="team-card-head">
            <div class="team-card-name">${position}. ${team.country}</div>
            ${statusBadge(team)}
          </div>
          <div class="team-card-meta">
            <span>${team.code || "n/a"}</span>
            <span>${formatMetric(metric, 3)} / 1k words</span>
            <span>${formatMetric(team.swears_per_100_comments, 2)} / 100 comments</span>
          </div>
          <div class="meter-track" aria-label="${team.country} profanity meter">
            <div class="meter-fill ${meterClass(metric)}" data-width="${width}" style="width: 0%"></div>
          </div>
        </article>
      `;
    }

    function animateMeters(root) {
      requestAnimationFrame(() => {
        root.querySelectorAll(".meter-fill").forEach(fill => {
          fill.style.width = `${fill.dataset.width || 0}%`;
        });
      });
    }

    function renderGroup(groupIndex) {
      const group = tournament.groups[groupIndex] || tournament.groups[0];
      groupLetter.textContent = group.group;
      teamGrid.innerHTML = group.teams.map((team, index) => renderTeamCard(team, index + 1)).join("");
      animateMeters(teamGrid);
    }

    function renderThirds(showQualified) {
      const qualified = new Set(tournament.third_place.qualified.map(team => team.country));
      document.getElementById("thirdKey").textContent = showQualified ? tournament.third_place.qualifier_group_key : "12";
      thirdTitle.textContent = showQualified ? "Eight survive the cut" : "Third-place table";
      thirdGrid.innerHTML = tournament.third_place.all.map((team, index) => {
        const row = renderTeamRow(team, { position: index + 1, thirdQualified: showQualified && qualified.has(team.country) });
        return row.replace('<div class="team-row', `<div style="--delay: ${Math.min(index, 7) * 55}ms" class="team-row`);
      }).join("");
    }

    function isChampionPath(match) {
      return match.winner && tournament.champion && match.winner.country === tournament.champion.country;
    }

    function renderMatchTeam(match, team) {
      if (!team) {
        return `
          <div class="match-row">
            <div class="team-name">TBD</div>
            <div class="metric">n/a</div>
          </div>
        `;
      }
      const winnerClass = match.winner && team.country === match.winner.country ? " winner" : "";
      return `
        <div class="match-row${winnerClass}">
          <div class="team-name">${team.country}<span class="team-code"> ${team.code || ""}</span></div>
          <div class="metric">${formatMetric(team.swears_per_1000_words)}</div>
        </div>
      `;
    }

    function renderBracketRound(roundIndex) {
      const round = tournament.bracket[roundIndex] || tournament.bracket[0];
      roundTitle.textContent = round.round;
      liveRound.textContent = round.round;
      bracketRounds.innerHTML = round.matches.map((match, index) => `
        <article class="match-card${isChampionPath(match) ? " champion-path" : ""}" style="--delay: ${Math.min(index, 11) * 45}ms">
          <div class="match-slot">${match.slot} | ${match.source_a} vs ${match.source_b}</div>
          ${renderMatchTeam(match, match.team_a)}
          ${renderMatchTeam(match, match.team_b)}
          ${match.warnings.length ? `<div class="match-warn">${match.warnings.join("<br>")}</div>` : ""}
        </article>
      `).join("");
    }

    function renderChampion() {
      document.getElementById("championCode").textContent = tournament.champion.country;
      document.getElementById("championStat").textContent =
        `${formatMetric(tournament.champion.swears_per_1000_words, 3)} swears per 1,000 words | ${tournament.champion.sample_status}`;
    }

    function awardName(award) {
      if (!award || !award.winner) return "Not available";
      if (award.id === "top_swear_match") {
        return `${award.winner.team_a || "Unknown"} vs ${award.winner.team_b || "Unknown"}`;
      }
      if (award.id === "top_swear_word") return award.winner.word;
      return award.winner.country;
    }

    function awardMetricLabel(award) {
      if (!award) return "n/a";
      return award.metric.replaceAll("_", " ");
    }

    function renderAwards() {
      awardButtons.innerHTML = availableAwards.map(award => `
        <button type="button" data-award="${award.id}" class="${award.id === activeAward ? "active" : ""}">${award.label}</button>
      `).join("");
      awardButtons.querySelectorAll("[data-award]").forEach(button => {
        button.addEventListener("click", () => {
          activeAward = button.dataset.award;
          updateAwardSpotlight();
        });
      });
      updateAwardSpotlight();
    }

    function updateAwardSpotlight() {
      const award = availableAwards.find(item => item.id === activeAward) || availableAwards[0];
      if (!award) return;
      document.querySelectorAll("[data-award]").forEach(button => {
        button.classList.toggle("active", button.dataset.award === award.id);
      });
      document.getElementById("awardLabel").textContent = award.label;
      document.getElementById("awardWinner").textContent = awardName(award);
      document.getElementById("awardNote").textContent = award.eligibility_note;
      document.getElementById("awardMetric").textContent = awardMetricLabel(award);
      document.getElementById("awardValue").textContent = formatMetric(award.value, award.metric === "count" ? 0 : 3);
    }

    function renderPhaseOptions() {
      phaseSelect.innerHTML = steps.map((step, index) => `<option value="${index}">${step.label}</option>`).join("");
      phaseSelect.addEventListener("change", () => {
        stopPlayback();
        setStep(Number(phaseSelect.value));
      });
    }

    function renderDots() {
      dots.innerHTML = steps.map((step, index) => `
        <button type="button" class="dot" data-step="${index}" aria-label="${step.label}"></button>
      `).join("");
      dots.querySelectorAll("[data-step]").forEach(dot => {
        dot.addEventListener("click", () => {
          stopPlayback();
          setStep(Number(dot.dataset.step));
        });
      });
    }

    function activatePhase(phaseName) {
      phases.forEach(phase => {
        phase.classList.toggle("active", phase.dataset.phase === phaseName);
      });
    }

    function renderCurrentStep(step) {
      activatePhase(step.phase);
      phaseLabel.textContent = step.label;

      if (step.phase === "groups") renderGroup(step.groupIndex);
      if (step.phase === "third") renderThirds(step.qualified);
      if (step.phase === "bracket") renderBracketRound(step.roundIndex);
      if (step.phase === "champion") renderChampion();
    }

    function setStep(nextIndex) {
      stepIndex = Math.max(0, Math.min(steps.length - 1, nextIndex));
      const step = steps[stepIndex];
      phaseSelect.value = String(stepIndex);
      stepStatus.textContent = `${stepIndex + 1} of ${steps.length}: ${step.label}`;
      renderCurrentStep(step);
      document.querySelectorAll(".dot").forEach(dot => {
        dot.classList.toggle("on", Number(dot.dataset.step) === stepIndex);
      });
      updatePlayButton();
    }

    function updatePlayButton() {
      const playBtn = document.getElementById("playBtn");
      playBtn.textContent = stepIndex >= steps.length - 1 ? "Replay" : "Play";
      playBtn.setAttribute("aria-pressed", "false");
    }

    function stopPlayback() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      updatePlayButton();
    }

    function playOneStep() {
      stopPlayback();
      if (stepIndex >= steps.length - 1) setStep(0);
      else setStep(stepIndex + 1);
    }

    renderAwards();
    renderPhaseOptions();
    renderDots();
    renderGroup(0);
    renderThirds(false);
    renderBracketRound(0);
    document.getElementById("prevBtn").addEventListener("click", () => {
      stopPlayback();
      setStep(stepIndex - 1);
    });
    document.getElementById("nextBtn").addEventListener("click", () => {
      stopPlayback();
      setStep(stepIndex + 1);
    });
    document.getElementById("playBtn").addEventListener("click", playOneStep);
    setStep(0);
  </script>
</body>
</html>
"""

def main():
    args = parse_args()
    match_config = load_json(args.match_config)
    leaderboard_rows = load_json(args.leaderboard)
    tournament = build_tournament_data(
        match_config,
        leaderboard_rows,
        scored_dir=args.scored_dir,
        population_path=args.population,
    )

    tournament_output = Path(args.tournament_output)
    match_output = Path(args.match_output)
    html_output = Path(args.html_output)
    tournament_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.parent.mkdir(parents=True, exist_ok=True)

    tournament_output.write_text(
        json.dumps(tournament, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    match_output.write_text(
        json.dumps(tournament["match_metrics"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    html = HTML_TEMPLATE.replace(
        "__DATA__",
        json.dumps(tournament, ensure_ascii=False, separators=(",", ":")),
    )
    html_output.write_text(html, encoding="utf-8")

    print(f"Wrote {tournament_output}")
    print(f"Wrote {match_output}")
    print(f"Wrote {html_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
