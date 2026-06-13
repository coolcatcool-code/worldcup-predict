#!/usr/bin/env python3
"""
Auto-update World Cup scores and standings from ESPN API.
Runs via GitHub Actions every 2 hours.
"""
import json, urllib.request, datetime, os, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

# ESPN abbreviation → our fixtures.json team name
TEAM_MAP = {
    "MEX": "Mexico",
    "RSA": "South Africa", "ZAF": "South Africa",
    "KOR": "Korea Republic",
    "CZE": "Czechia",
    "CAN": "Canada",
    "BIH": "Bosnia and Herzegovina",
    "QAT": "Qatar",
    "SUI": "Switzerland",
    "BRA": "Brazil",
    "MAR": "Morocco",
    "HTI": "Haiti", "HAI": "Haiti",
    "SCO": "Scotland",
    "USA": "United States",
    "PAR": "Paraguay",
    "AUS": "Australia",
    "TUR": "Türkiye",
    "GER": "Germany",
    "CUW": "Curaçao",
    "CIV": "Ivory Coast",
    "ECU": "Ecuador",
    "NED": "Netherlands",
    "JPN": "Japan",
    "SWE": "Sweden",
    "TUN": "Tunisia",
    "BEL": "Belgium",
    "EGY": "Egypt",
    "IRN": "Iran",
    "NZL": "New Zealand",
    "ESP": "Spain",
    "CPV": "Cape Verde",
    "KSA": "Saudi Arabia",
    "URU": "Uruguay",
    "FRA": "France",
    "SEN": "Senegal",
    "IRQ": "Iraq",
    "NOR": "Norway",
    "ARG": "Argentina",
    "ALG": "Algeria",
    "AUT": "Austria",
    "JOR": "Jordan",
    "POR": "Portugal",
    "COD": "DR Congo",
    "UZB": "Uzbekistan",
    "COL": "Colombia",
    "ENG": "England",
    "CRO": "Croatia",
    "GHA": "Ghana",
    "PAN": "Panama",
}

def fetch_espn(date_str):
    """Fetch ESPN scoreboard for YYYY-MM-DD, return list of parsed events."""
    d = date_str.replace("-", "")
    url = f"{ESPN_BASE}?dates={d}&limit=20"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"  ESPN fetch failed for {date_str}: {e}")
        return []

    results = []
    for ev in data.get("events", []):
        comp = ev.get("competitions", [{}])[0]
        status = comp.get("status", {}).get("type", {})
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue
        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
        h_abv = home.get("team", {}).get("abbreviation", "").upper()
        a_abv = away.get("team", {}).get("abbreviation", "").upper()
        h_name = TEAM_MAP.get(h_abv, home.get("team", {}).get("displayName", h_abv))
        a_name = TEAM_MAP.get(a_abv, away.get("team", {}).get("displayName", a_abv))
        state = status.get("state", "pre")       # pre / in / post
        completed = status.get("completed", False)
        h_score = home.get("score", "0")
        a_score = away.get("score", "0")
        results.append({
            "home": h_name,
            "away": a_name,
            "h_abv": h_abv,
            "a_abv": a_abv,
            "score": f"{h_score}-{a_score}",
            "state": state,
            "completed": completed,
        })
    return results

def names_match(a, b):
    """Fuzzy team name match."""
    a, b = a.lower().strip(), b.lower().strip()
    if a == b: return True
    # common aliases
    aliases = {
        "united states": "usa",
        "ivory coast": "côte d'ivoire",
        "dr congo": "congo dr",
        "korea republic": "south korea",
        "türkiye": "turkey",
        "curaçao": "curacao",
    }
    a = aliases.get(a, a)
    b = aliases.get(b, b)
    return a == b or a[:4] == b[:4]

def update_fixtures(fixtures, espn_events):
    """Merge ESPN scores into fixtures list. Returns (updated_count, changed)."""
    updated = 0
    for ev in espn_events:
        for m in fixtures:
            if names_match(m["home"], ev["home"]) and names_match(m["away"], ev["away"]):
                new_score = ev["score"] if ev["completed"] or ev["state"] == "post" else None
                new_status = "done" if ev["completed"] else ("live" if ev["state"] == "in" else "pre")
                changed = False
                if new_score and m.get("score") != new_score:
                    m["score"] = new_score
                    changed = True
                if m.get("status") != new_status:
                    m["status"] = new_status
                    changed = True
                if changed:
                    updated += 1
                break
    return updated

def compute_standings(fixtures, groups_map):
    """Recompute group standings from completed fixtures."""
    # Init table
    table = {}
    for grp, teams in groups_map.items():
        table[grp] = {}
        for t in teams:
            table[grp][t] = {"code": t, "name": t, "flag": "", "mp": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "gd": 0, "pts": 0}

    for m in fixtures:
        if m.get("round") != "group": continue
        score = m.get("score")
        if not score or m.get("status") not in ("done", "post"): continue
        grp = m.get("group")
        if not grp or grp not in table: continue
        try:
            hg, ag = map(int, score.split("-"))
        except:
            continue
        home, away = m["home"], m["away"]
        if home not in table[grp] or away not in table[grp]: continue
        ht = table[grp][home]
        at = table[grp][away]
        ht["mp"] += 1; at["mp"] += 1
        ht["gf"] += hg; ht["ga"] += ag
        at["gf"] += ag; at["ga"] += hg
        ht["gd"] = ht["gf"] - ht["ga"]
        at["gd"] = at["gf"] - at["ga"]
        if hg > ag:
            ht["w"] += 1; ht["pts"] += 3
            at["l"] += 1
        elif hg < ag:
            at["w"] += 1; at["pts"] += 3
            ht["l"] += 1
        else:
            ht["d"] += 1; ht["pts"] += 1
            at["d"] += 1; at["pts"] += 1

    # Sort each group
    def sort_key(t):
        return (-t["pts"], -t["gd"], -t["gf"])

    return {grp: sorted(teams.values(), key=sort_key) for grp, teams in table.items()}

def main():
    now_utc = datetime.datetime.utcnow()
    # Fetch ESPN for yesterday, today, tomorrow (to catch late-finishing matches)
    dates = [(now_utc + datetime.timedelta(days=d)).strftime("%Y-%m-%d") for d in (-1, 0, 1)]

    print(f"Fetching ESPN for dates: {dates}")
    all_events = []
    for d in dates:
        evs = fetch_espn(d)
        print(f"  {d}: {len(evs)} events")
        all_events.extend(evs)

    # Load fixtures
    fixtures_path = DATA / "fixtures.json"
    with open(fixtures_path, encoding="utf-8") as f:
        fixtures_data = json.load(f)

    matches = fixtures_data["matches"]
    groups_map = fixtures_data["groups"]

    # Update scores
    updated = update_fixtures(matches, all_events)
    print(f"Updated {updated} fixtures")

    # Recompute standings
    standings = compute_standings(matches, groups_map)
    beijing_now = (now_utc + datetime.timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # Write fixtures.json
    with open(fixtures_path, "w", encoding="utf-8") as f:
        json.dump(fixtures_data, f, ensure_ascii=False, separators=(",", ":"))
    print("Wrote fixtures.json")

    # Write standings.json
    standings_path = DATA / "standings.json"
    with open(standings_path, "w", encoding="utf-8") as f:
        json.dump({"updatedAt": beijing_now, "groups": standings}, f, ensure_ascii=False, separators=(",", ":"))
    print("Wrote standings.json")

    # Summary
    done = sum(1 for m in matches if m.get("status") == "done")
    live = sum(1 for m in matches if m.get("status") == "live")
    print(f"Done: {done} matches | Live: {live} matches | Total: {len(matches)}")

if __name__ == "__main__":
    main()
