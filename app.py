"""Canadian-Traveler-style online navigation experiment (Streamlit pilot)."""
import csv, hashlib, heapq, io, os, sqlite3, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

# Set ROUTE_STUDY_DB=/secure/path/route_study.sqlite on a university server.
# The default is convenient for a local pilot. Back up this file regularly.
DB_PATH = Path(os.environ.get("ROUTE_STUDY_DB", "data/route_study_fixed_v21_fuel_feasible_hindsight.sqlite"))
TASK_VERSION = "v21-fuel-feasible-hindsight"
# Credits per network. Set ROUTE_STUDY_SURVEILLANCE_LIMIT=0 to disable,
# or another small integer for a different experimental condition.
SURVEILLANCE_LIMIT = max(0, int(os.environ.get("ROUTE_STUDY_SURVEILLANCE_LIMIT", "2")))
# Detailed hindsight feedback can teach a participant before the next map.
# It is therefore deferred until the final debrief by default. Set to 1 only
# when between-level feedback is an intentional, separately labelled condition.
SHOW_BETWEEN_LEVEL_HINDSIGHT = os.environ.get("ROUTE_STUDY_SHOW_BETWEEN_LEVEL_HINDSIGHT", "0").strip().lower() in {"1", "true", "yes"}
# Fixed scenario seed: every participant sees identical open/closed roads in a map.
# Change only before launching a new, separately labelled study wave.
STUDY_REALIZATION_ID = os.environ.get("ROUTE_STUDY_REALIZATION_ID", "relief-routing-v10-richer-easy-fixed-a")


def init_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY, participant_id TEXT NOT NULL,
            age_band TEXT, gender TEXT, trial INTEGER, network TEXT,
            condition TEXT, difficulty TEXT, choice_class TEXT, objective TEXT, event TEXT, wallclock_utc TEXT,
            elapsed_seconds REAL, node TEXT, route_distance REAL, moves INTEGER,
            attempted_to TEXT, moved_to TEXT, edge TEXT, edge_cost REAL, optimum_realized REAL,
            excess_distance REAL, on_time TEXT,
            surveilled_edge TEXT, surveillance_number INTEGER, surveilled_open TEXT,
            survey_hindsight_relevant TEXT, realization_id TEXT, surveillance_limit INTEGER, task_version TEXT,
            fuel_before REAL, fuel_after REAL, fuel_capacity REAL, refuelled TEXT,
            level INTEGER
        )""")
        # Lightweight migration for databases created by earlier prototype versions.
        existing = {row[1] for row in con.execute("PRAGMA table_info(events)")}
        for name, sql_type in (
            ("difficulty", "TEXT"), ("choice_class", "TEXT"), ("moved_to", "TEXT"),
            ("surveilled_edge", "TEXT"), ("surveillance_number", "INTEGER"),
            ("surveilled_open", "TEXT"), ("survey_hindsight_relevant", "TEXT"),
            ("realization_id", "TEXT"), ("surveillance_limit", "INTEGER"), ("task_version", "TEXT"),
            ("fuel_before", "REAL"), ("fuel_after", "REAL"), ("fuel_capacity", "REAL"), ("refuelled", "TEXT"),
            ("level", "INTEGER"),
        ):
            if name not in existing:
                con.execute(f"ALTER TABLE events ADD COLUMN {name} {sql_type}")


def persist_event(record):
    """One short-lived connection per write is safe for a modest local pilot."""
    demographics = st.session_state.get("demographics", {})
    row = {"event_id": str(uuid.uuid4()), "age_band": demographics.get("age_band"),
           "gender": demographics.get("gender"), **record}
    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as con:
            con.execute(f"INSERT INTO events ({', '.join(columns)}) VALUES ({placeholders})",
                        [row[c] for c in columns])
    except sqlite3.Error as exc:
        # The on-screen session and final download remain usable; the message makes
        # a storage failure visible instead of silently losing the record.
        st.warning(f"Local data-storage error: {exc}")


init_database()

st.set_page_config(page_title="Disaster-relief route task", layout="wide")
# This local Streamlit component renders the map and sends the selected edge back
# only when a participant clicks an unrevealed road in scout mode.
clickable_edge_map = components.declare_component(
    "clickable_edge_map", path=str(Path(__file__).parent / "edge_map_component")
)

TUTORIAL_HTML = """<!doctype html><html><head><style>
body{margin:0;font-family:Arial,sans-serif;color:#0f172a;background:#f8fafc}.caption{font-size:14px;font-weight:700;fill:#1e3a8a}.small{font-size:12px;fill:#334155}.road{stroke:#94a3b8;stroke-width:5}.known{stroke:#16a34a;stroke-width:6}.blocked{stroke:#dc2626;stroke-width:5;stroke-dasharray:8 5}.label{fill:white;stroke:#cbd5e1;stroke-width:1}.pulse{animation:pulse 1.2s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}</style></head><body>
<svg viewBox="0 0 820 280" width="100%" height="280" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Animated map tutorial"><rect x="1" y="1" width="818" height="278" rx="10" fill="#f8fafc" stroke="#cbd5e1"/>
<text x="25" y="28" class="caption">How a delivery works</text><text x="25" y="49" class="small">Watch the truck, road status, and remote-check symbol.</text>
<line x1="105" y1="148" x2="350" y2="82" class="known"/><line x1="350" y1="82" x2="690" y2="148" class="road"/><line x1="105" y1="148" x2="350" y2="190" class="road"/><line x1="350" y1="190" x2="690" y2="148" class="blocked"/>
<g transform="translate(215,105)"><rect width="72" height="21" rx="7" class="label"/><text x="36" y="15" text-anchor="middle" class="small">2 | 80%</text></g><g transform="translate(500,94)"><rect width="72" height="21" rx="7" class="label"/><text x="36" y="15" text-anchor="middle" class="small">3 | 60%</text></g>
<circle cx="535" cy="89" r="11" fill="#2563eb" class="pulse"/><text x="535" y="94" text-anchor="middle" font-size="15" fill="white">D</text><text x="552" y="78" class="small">click to check</text>
<g><circle cx="105" cy="148" r="20" fill="#2563eb"/><text x="105" y="154" text-anchor="middle" fill="white" font-weight="bold">A</text><circle cx="350" cy="82" r="20" fill="white" stroke="#1e293b" stroke-width="2"/><text x="350" y="88" text-anchor="middle" font-weight="bold">X</text><circle cx="350" cy="190" r="20" fill="white" stroke="#1e293b" stroke-width="2"/><text x="350" y="196" text-anchor="middle" font-weight="bold">Y</text><g transform="translate(673,92)"><path d="M0 13L17 0 34 13" fill="#ef4444" stroke="#991b1b" stroke-width="2"/><rect x="5" y="13" width="24" height="17" fill="#fee2e2" stroke="#991b1b" stroke-width="2"/><path d="M17 7V17M12 12H22" stroke="#fff" stroke-width="2"/></g><circle cx="690" cy="148" r="20" fill="#2563eb"/><text x="690" y="154" text-anchor="middle" fill="white" font-weight="bold">B</text></g>
<g><rect x="-15" y="-9" width="20" height="15" rx="2" fill="#f97316" stroke="#7c2d12" stroke-width="1.5"/><path d="M5-6L13-6 18 0V6H5Z" fill="#fb923c" stroke="#7c2d12" stroke-width="1.5"/><circle cx="-8" cy="8" r="4" fill="#1e293b"/><circle cx="12" cy="8" r="4" fill="#1e293b"/><animateMotion path="M105,148 L350,82 L690,148" dur="6s" repeatCount="indefinite"/></g>
<g transform="translate(25,245)"><text class="small">1. Choose an adjacent road</text><text x="245" class="small">2. At either end, its true status is revealed</text><text x="545" class="small">3. Blue D = a drone check</text></g></svg></body></html>"""

def render_clickable_map(network, t, scout_enabled, credits_left):
    return clickable_edge_map(
        nodes=network["nodes"], edges=network["edges"], current=t["current"],
        start=network["start"], goal=network["goal"], revealed=list(t["revealed"]),
        states=t["states"], remotely_checked=list(t["surveillance_history"]),
        fuel_stations=network.get("fuel_stations", []), distance=t["distance"],
        objective=t["objective"], deadline=t["deadline"], fuel=t.get("fuel"),
        fuel_capacity=t.get("fuel_capacity"), scout_enabled=scout_enabled,
        credits_left=credits_left,
        key=f"edge-map-{st.session_state.trial}",
        default=None,
    )

# Each map has two robust routes and one tempting but uncertain shortcut.
# Every participant sees the same fixed open/closed realization for each map;
# statuses remain hidden until revealed. All maps remain solvable.
NETWORKS = [
 # Easy maps retain a clear expected-time recommendation, but now include
 # recovery links that create meaningful decisions after a road is revealed.
 {"level":1, "name":"Level 1: reliable corridor", "condition":"easy_risky_better", "difficulty":"easy", "start":"A", "goal":"B", "deadline":9,
  "description":"The upper corridor is short and highly reliable, but recovery links into the longer lower corridor create choices if a bridge fails. The lower corridor is certain.", "surveillance_limit":1,
  "choice_classes":{"X":"risky","C":"safe"}, "guaranteed_path":[("A","C"),("C","D"),("D","E"),("E","B")],
  "nodes":{"A":(7,55),"X":(24,15),"Y":(43,14),"Z":(64,16),"C":(22,85),"D":(46,85),"E":(70,85),"B":(94,55)},
  "edges":[("A","X",2,0),("X","Y",1,.05),("Y","Z",1,.05),("Z","B",1,.05),("A","C",3,0),("C","D",2,0),("D","E",2,0),("E","B",3,0),("X","D",4,.20),("Y","D",3,.25),("Z","E",3,.25)]},
 {"level":2, "name":"Level 2: fragile corridor", "condition":"easy_safe_better", "difficulty":"easy", "start":"A", "goal":"B", "deadline":10,
  "description":"The upper corridor is short but its bridges are unlikely to be passable. Recovery links exist, yet the lower corridor remains the reliable way to deliver supplies.", "surveillance_limit":1,
  "choice_classes":{"X":"risky","C":"safe"}, "guaranteed_path":[("A","C"),("C","D"),("D","E"),("E","B")],
  "nodes":{"A":(7,55),"X":(24,15),"Y":(43,14),"Z":(64,16),"C":(22,85),"D":(46,85),"E":(70,85),"B":(94,55)},
  "edges":[("A","X",2,0),("X","Y",1,.60),("Y","Z",1,.60),("Z","B",1,.60),("A","C",3,0),("C","D",2,0),("D","E",2,0),("E","B",3,0),("X","D",4,.25),("Y","D",3,.30),("Z","E",3,.30)]},
 # Hard: a larger, fuel-constrained relief network. Several uncertain branches
 # look attractive, but a truck with a limited range must plan known refuelling stops.
 {"level":3, "name":"Level 3: fuel-constrained corridor", "condition":"hard_fuel_corridor", "difficulty":"hard", "start":"A", "goal":"B", "deadline":18,
  "description":"A larger regional network. The truck has fuel for 10 travel-time units and automatically refuels at the marked fuel depots F1 and F2. Several short uncertain roads compete with longer routes that reliably reach fuel.", "surveillance_limit":2, "fuel_capacity":10, "fuel_stations":["F1","F2"],
  "choice_classes":{"R":"risky","C":"safe"}, "guaranteed_path":[("A","C"),("C","F1"),("F1","D"),("D","F2"),("F2","G"),("G","B")],
  "nodes":{"A":(6,53),"R":(20,53),"X":(36,16),"Y":(52,13),"Z":(70,18),"M":(48,40),"Q":(70,42),"C":(28,84),"F1":(45,82),"D":(60,78),"F2":(75,81),"G":(86,69),"B":(95,52)},
  "edges":[("A","R",2,0),("R","X",2,0),("X","Y",2,.20),("Y","Z",2,.35),("Z","B",2,.25),("X","M",3,.30),("M","Q",2,.35),("Q","B",3,.25),("Y","Q",2,.40),("A","C",3,0),("R","C",3,0),("C","F1",2,0),("F1","D",3,0),("D","F2",2,0),("F2","G",2,0),("G","B",3,0),("F1","M",3,.30),("M","D",2,.25),("Q","G",3,.35),("D","G",2,.30)]},
 # Hard: a city-scale information network with multiple contingencies and two fuel depots.
 # The coordination node reveals local roads, but neither it nor two remote checks resolves all choices.
 {"level":4, "name":"Level 4: regional coordination challenge", "condition":"hard_regional_information", "difficulty":"challenge", "start":"A", "goal":"B", "deadline":19,
  "description":"Final challenge: coordinate a regional delivery network with two fuel depots (F1, F2), several uncertain links, and limited drone checks. The truck holds 9 travel-time units of fuel. Take your time to inspect the full map before committing.", "surveillance_limit":2, "fuel_capacity":9, "fuel_stations":["F1","F2"],
  "choice_classes":{"H":"scout","C":"safe"}, "guaranteed_path":[("A","C"),("C","F1"),("F1","D"),("D","F2"),("F2","E"),("E","B")],
  "nodes":{"A":(5,54),"H":(22,52),"X":(38,13),"Y":(48,33),"Z":(66,15),"W":(78,34),"P":(43,61),"Q":(66,59),"C":(20,88),"F1":(38,86),"D":(55,87),"F2":(72,86),"E":(84,73),"B":(96,53)},
  "edges":[("A","H",2,0),("H","X",2,0),("X","Z",2,.35),("Z","B",3,.45),("H","Y",2,0),("Y","Z",2,.30),("Y","P",2,.25),("P","Q",2,.30),("Q","W",2,.30),("W","B",3,.25),("Z","W",2,.35),("H","P",3,0),("P","F1",3,.20),("Q","F2",3,.20),("A","C",3,0),("C","F1",2,0),("F1","D",3,0),("D","F2",2,0),("F2","E",2,0),("E","B",3,0),("D","Q",3,.25),("F2","W",3,.30),("Y","F1",3,.30)]}
]


def edge_key(u,v): return "|".join(sorted((u,v)))
def stable_uniform(*parts):
    h=hashlib.sha256("|".join(map(str,parts)).encode()).hexdigest()
    return int(h[:12],16)/16**12

def state_for(network):
    """Return the fixed, participant-invariant scenario for this named map."""
    states={}
    for u,v,_,p in network['edges']:
        states[edge_key(u,v)] = stable_uniform(STUDY_REALIZATION_ID, network["condition"], u, v) >= p
    # Guarantee one complete route, preventing an impossible trial.
    for e in network['guaranteed_path']: states[edge_key(*e)] = True
    return states

def shortest_distance_from(network, states, start):
    graph={n:[] for n in network['nodes']}
    for u,v,w,_ in network['edges']:
        if states[edge_key(u,v)]: graph[u].append((v,w)); graph[v].append((u,w))
    q=[(0,start)]; seen={}
    while q:
        d,u=heapq.heappop(q)
        if u in seen: continue
        seen[u]=d
        if u==network['goal']: return d
        for v,w in graph[u]: heapq.heappush(q,(d+w,v))
    return None

def shortest_distance(network, states):
    return shortest_distance_from(network, states, network["start"])

def shortest_path(network, states):
    """Shortest realised A-to-B route that the truck can actually drive.

    On fuel maps, Dijkstra's state includes both location and remaining fuel.
    Reaching a fuel-station node refills the tank. This avoids incorrectly
    displaying a geometrically short route that exceeds tank range as hindsight
    feedback.
    """
    graph={n:[] for n in network["nodes"]}
    for u,v,w,_ in network["edges"]:
        if states[edge_key(u,v)]:
            graph[u].append((v,w)); graph[v].append((u,w))
    start, goal = network["start"], network["goal"]
    capacity=network.get("fuel_capacity")
    if capacity is None:
        q=[(0,start)]; best={start:0}; parent={start:None}
        while q:
            d,u=heapq.heappop(q)
            if d != best.get(u):
                continue
            if u==goal:
                path=[]
                while u is not None:
                    path.append(u); u=parent[u]
                return d,list(reversed(path))
            for v,w in graph[u]:
                candidate=d+w
                if candidate < best.get(v,float("inf")):
                    best[v]=candidate; parent[v]=u; heapq.heappush(q,(candidate,v))
        return None,[]

    # A state is (node, fuel remaining). Fuel values are integral travel units in
    # these maps; retaining the value makes refuelling feasibility explicit.
    initial=(start, capacity)
    q=[(0, start, capacity)]
    best={initial:0}; parent={initial:None}
    terminal=None
    stations=set(network.get("fuel_stations", []))
    while q:
        d,u,fuel=heapq.heappop(q)
        state=(u,fuel)
        if d != best.get(state):
            continue
        if u==goal:
            terminal=state
            break
        for v,w in graph[u]:
            if w > fuel:
                continue
            next_fuel=fuel-w
            if v in stations:
                next_fuel=capacity
            next_state=(v,next_fuel)
            candidate=d+w
            if candidate < best.get(next_state,float("inf")):
                best[next_state]=candidate; parent[next_state]=state
                heapq.heappush(q,(candidate,v,next_fuel))
    if terminal is None:
        return None,[]
    path=[]; state=terminal
    while state is not None:
        path.append(state[0]); state=parent[state]
    return best[terminal],list(reversed(path))

def surveillance_hindsight_relevant(network, states, current, edge):
    """Would learning this road's realized state change the hindsight shortest remaining trip?

    This ex-post flag is a target-relevance diagnostic, not a claim that a player
    could have known the answer before surveying.
    """
    baseline = shortest_distance_from(network, states, current)
    alternate = dict(states); alternate[edge] = not alternate[edge]
    changed = shortest_distance_from(network, alternate, current)
    return baseline != changed

def render(network, current, revealed, states, remotely_checked, distance, objective, deadline, fuel=None, fuel_capacity=None, movement_from=None, movement_started_at=None):
    """Draw the task map with in-map road, travel-time, and fuel feedback."""
    lines=[]
    for u,v,w,p_closed in network['edges']:
        x1,y1=network['nodes'][u]; x2,y2=network['nodes'][v]; k=edge_key(u,v)
        if k in revealed: color="#16a34a" if states[k] else "#dc2626"; dash="" if states[k] else "7,5"; width=4
        else: color="#94a3b8"; dash=""; width=3
        label = f"{w} · checked" if k in remotely_checked else (f"{w}" if k in revealed else f"{w} · {round((1-p_closed)*100)}% open")
        lines.append(f'<line x1="{x1*8}" y1="{y1*4}" x2="{x2*8}" y2="{y2*4}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/><rect x="{(x1+x2)*4-30}" y="{(y1+y2)*2-16}" width="60" height="19" rx="7" fill="#ffffff" fill-opacity=".88"/><text x="{(x1+x2)*4}" y="{(y1+y2)*2-3}" text-anchor="middle" font-size="13" fill="#0f172a">{label}</text>')
    nodes=[]
    for n,(x,y) in network['nodes'].items():
        is_station=n in network.get("fuel_stations", [])
        fill="#f59e0b" if n==current else ("#2563eb" if n in (network['start'],network['goal']) else ("#dcfce7" if is_station else "#fff"))
        pump=(f'<g transform="translate({x*8-13},{y*4-42})"><rect x="0" y="0" width="18" height="24" rx="3" fill="#15803d"/><rect x="4" y="4" width="10" height="8" rx="1" fill="#dcfce7"/><path d="M18 7 C26 7,26 18,22 18 L20 18" fill="none" stroke="#15803d" stroke-width="3"/><circle cx="9" cy="18" r="2" fill="#dcfce7"/></g>' if is_station else '')
        # The community destination at B has an explicit shelter pictogram.
        shelter=(f'<g transform="translate({x*8-17},{y*4-48})"><path d="M0 13 L17 0 L34 13" fill="#ef4444" stroke="#991b1b" stroke-width="2"/><rect x="5" y="13" width="24" height="17" rx="2" fill="#fee2e2" stroke="#991b1b" stroke-width="2"/><rect x="14" y="20" width="6" height="10" fill="#991b1b"/><path d="M17 7 V17 M12 12 H22" stroke="#fff" stroke-width="2"/></g>' if n==network['goal'] else '')
        nodes.append(pump+shelter+f'<circle cx="{x*8}" cy="{y*4}" r="16" fill="{fill}" stroke="#1e293b" stroke-width="2"/><text x="{x*8}" y="{y*4+5}" text-anchor="middle" font-size="15" font-weight="bold">{n}</text>')
    cx,cy=network['nodes'][current][0]*8,network['nodes'][current][1]*4
    truck_shape='<g><rect x="-15" y="-9" width="20" height="15" rx="2" fill="#f97316" stroke="#7c2d12" stroke-width="1.5"/><path d="M5,-6 L13,-6 L18,0 L18,6 L5,6 Z" fill="#fb923c" stroke="#7c2d12" stroke-width="1.5"/><rect x="8" y="-4" width="5" height="4" fill="#dbeafe"/><circle cx="-8" cy="8" r="4" fill="#1e293b"/><circle cx="12" cy="8" r="4" fill="#1e293b"/><path d="M-9,-5 L-3,-5 L-6,1 Z" fill="#fff"/></g>'
    if movement_from and movement_from in network['nodes'] and movement_started_at and time.time()-movement_started_at < 1.5:
        px,py=network['nodes'][movement_from][0]*8,network['nodes'][movement_from][1]*4
        truck=f'<g>{truck_shape}<animateMotion path="M {px},{py} L {cx},{cy}" dur="0.85s" fill="freeze"/></g>'
        animate='<text x="20" y="28" font-size="14" fill="#9a3412" font-weight="bold">Relief truck en route…</text>'
    else:
        truck=f'<g transform="translate({cx},{cy})">{truck_shape}</g>'; animate=""
    delivered=current == network['goal']
    delivery_color="#16a34a" if delivered else "#2563eb"
    delivery_label="DELIVERED" if delivered else "EN ROUTE"
    legend='<g transform="translate(18,385)"><rect x="0" y="0" width="400" height="24" rx="6" fill="#ffffff" fill-opacity=".94"/><circle cx="15" cy="12" r="5" fill="#f59e0b"/><text x="26" y="16" font-size="12">truck</text><circle cx="86" cy="12" r="5" fill="#16a34a"/><text x="97" y="16" font-size="12">passable</text><circle cx="175" cy="12" r="5" fill="#dc2626"/><text x="186" y="16" font-size="12">blocked</text><rect x="247" y="5" width="10" height="14" rx="2" fill="#15803d"/><text x="266" y="16" font-size="12">fuel depot</text></g>'
    destination=f'<g transform="translate(460,382)"><rect x="0" y="0" width="340" height="29" rx="7" fill="#fff7ed" stroke="#fdba74"/><circle cx="20" cy="14" r="7" fill="#2563eb"/><text x="20" y="18" text-anchor="middle" font-size="10" fill="#fff" font-weight="bold">A</text><path d="M32 14 H202" stroke="#94a3b8" stroke-width="2" stroke-dasharray="4,3"/><path d="M110 8 L121 14 L110 20 Z" fill="{delivery_color}"/><path d="M213 12 L225 3 L237 12" fill="#ef4444" stroke="#991b1b" stroke-width="1"/><rect x="217" y="12" width="16" height="10" fill="#fee2e2" stroke="#991b1b" stroke-width="1"/><text x="246" y="12" font-size="10" font-weight="bold" fill="#9a3412">SHELTER B</text><text x="246" y="23" font-size="10" fill="{delivery_color}">{delivery_label}</text></g>'
    if objective == "deadline":
        limit=max(float(deadline or 1),1); ratio=min(distance/limit,1); time_color="#2563eb" if distance <= limit else "#dc2626"; time_title="DELIVERY TIME / LIMIT"; time_value=f"{distance} / {deadline}"; time_subtitle="time units travelled"
    else:
        ratio=min(distance/max(distance+3,8),1); time_color="#2563eb"; time_title="DELIVERY TIME"; time_value=str(distance); time_subtitle="time units travelled · minimise"
    time_bar=round(220*ratio,1)
    if fuel_capacity is not None:
        fuel_ratio=max(0,min(float(fuel)/float(fuel_capacity),1)); fuel_bar=round(220*fuel_ratio,1); fuel_color="#15803d" if fuel_ratio>.30 else "#dc2626"; fuel_value=f"{fuel} / {fuel_capacity}"; fuel_subtitle="refill at pump icons"
    else:
        fuel_bar=220; fuel_color="#64748b"; fuel_value="—"; fuel_subtitle="no fuel constraint"
    dashboard=f"""<g transform="translate(18,418)"><rect x="0" y="0" width="370" height="43" rx="8" fill="#eff6ff" stroke="#93c5fd"/><circle cx="19" cy="17" r="10" fill="none" stroke="#2563eb" stroke-width="2"/><path d="M19 17 L19 10 M19 17 L24 20" stroke="#2563eb" stroke-width="2"/><text x="38" y="14" font-size="10" font-weight="bold" fill="#1e3a8a">{time_title}</text><text x="38" y="29" font-size="16" font-weight="bold" fill="#0f172a">{time_value}</text><text x="96" y="29" font-size="10" fill="#475569">{time_subtitle}</text><rect x="140" y="34" width="220" height="5" rx="3" fill="#cbd5e1"/><rect x="140" y="34" width="{time_bar}" height="5" rx="3" fill="{time_color}"/></g><g transform="translate(432,418)"><rect x="0" y="0" width="370" height="43" rx="8" fill="#f0fdf4" stroke="#86efac"/><g transform="translate(11,6)"><rect x="0" y="0" width="15" height="21" rx="2" fill="#15803d"/><rect x="3" y="3" width="9" height="7" fill="#dcfce7"/><path d="M15 6 C21 6,21 16,18 16" fill="none" stroke="#15803d" stroke-width="2"/></g><text x="38" y="14" font-size="10" font-weight="bold" fill="#166534">FUEL RESERVE</text><text x="38" y="29" font-size="16" font-weight="bold" fill="#0f172a">{fuel_value}</text><text x="96" y="29" font-size="10" fill="#475569">{fuel_subtitle}</text><rect x="140" y="34" width="220" height="5" rx="3" fill="#bbf7d0"/><rect x="140" y="34" width="{fuel_bar}" height="5" rx="3" fill="{fuel_color}"/></g>"""
    st.markdown('<svg viewBox="0 0 820 470" width="100%" style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px">'+''.join(lines+nodes)+truck+animate+legend+destination+dashboard+'</svg>', unsafe_allow_html=True)

def initialise_trial():
    i=st.session_state.trial
    net=NETWORKS[st.session_state.network_order[i]]
    states=state_for(net)
    optimum, optimum_path=shortest_path(net,states)
    # Objective order is counterbalanced: alternating by participant hash.
    objective = ("deadline" if (i + int(stable_uniform(st.session_state.pid,'order')*2))%2 else "speed")
    all_open={edge_key(a,b): True for a,b,_,_ in net['edges']}
    # The deadline is fixed for a map, not tailored to its realized closures.
    # It is therefore a pre-specified experimental manipulation.
    deadline=net.get('deadline', shortest_distance(net, all_open)+3) if objective=='deadline' else None
    st.session_state.t={"network":net,"states":states,"objective":objective,"current":net['start'],"revealed":set(),"distance":0,"moves":0,"start_time":time.time(),"events":[],"deadline":deadline,"optimum":optimum,
                        "surveillance_limit":net.get("surveillance_limit", SURVEILLANCE_LIMIT), "surveillances_used":0,
                        "surveillance_history":[], "last_survey_result":None, "optimum_path":optimum_path,
                        "fuel_capacity":net.get("fuel_capacity"), "fuel":net.get("fuel_capacity")}
    reveal_adjacent()

def reveal_adjacent():
    t=st.session_state.t; u=t['current']
    for a,b,_,_ in t['network']['edges']:
        if u in (a,b): t['revealed'].add(edge_key(a,b))

def neighbours():
    t=st.session_state.t; u=t['current']; out=[]
    for a,b,w,_ in t['network']['edges']:
        if u==a: out.append((b,w))
        if u==b: out.append((a,w))
    return out

def is_stranded():
    """True when no currently usable road leaves the truck's current node."""
    t=st.session_state.t
    if t["current"] == t["network"]["goal"]:
        return False
    for v, w in neighbours():
        k=edge_key(t["current"], v)
        if t["states"][k] and (t.get("fuel") is None or w <= t["fuel"]):
            return False
    return True

def log_event(kind, **extra):
    t=st.session_state.t
    record={"participant_id":st.session_state.pid,"trial":st.session_state.trial+1,"level":t['network'].get('level', st.session_state.trial+1),"network":t['network']['name'],"condition":t['network'].get('condition'),"difficulty":t['network'].get('difficulty'),"realization_id":STUDY_REALIZATION_ID,"task_version":TASK_VERSION,"surveillance_limit":t['surveillance_limit'],"objective":t['objective'],"event":kind,"wallclock_utc":datetime.now(timezone.utc).isoformat(),"elapsed_seconds":round(time.time()-t['start_time'],3),"node":t['current'],"route_distance":t['distance'],"moves":t['moves'], "fuel_before": extra.pop("fuel_before", t.get("fuel")),
            "fuel_after": extra.pop("fuel_after", t.get("fuel")), "fuel_capacity":t.get("fuel_capacity"), **extra}
    t['events'].append(record)
    persist_event(record)

def surveillance_candidates():
    """All unrevealed roads can be checked remotely; adjacent roads are already revealed."""
    t=st.session_state.t
    return [(a, b, w, p) for a, b, w, p in t["network"]["edges"]
            if edge_key(a, b) not in t["revealed"]]

def survey_edge(a, b):
    t=st.session_state.t; k=edge_key(a, b)
    # Guard against repeat clicks/stale widgets and make every credit auditable.
    if t["surveillances_used"] >= t["surveillance_limit"] or k in t["revealed"]:
        return
    t["revealed"].add(k)
    t["surveillances_used"] += 1
    t["surveillance_history"].append(k)
    t["last_survey_result"] = {"edge": f"{a}–{b}", "open": bool(t["states"][k])}
    log_event("surveillance", surveilled_edge=k,
              surveillance_number=t["surveillances_used"],
              surveilled_open=str(bool(t["states"][k])),
              survey_hindsight_relevant=str(surveillance_hindsight_relevant(
                  t["network"], t["states"], t["current"], k)))

def move(v,w):
    t=st.session_state.t; k=edge_key(t['current'],v)
    if not t['states'][k]:
        log_event('attempt_closed_edge', attempted_to=v, edge=k); return
    if t.get("fuel") is not None and w > t["fuel"]:
        log_event('insufficient_fuel', attempted_to=v, edge=k, edge_cost=w,
                  fuel_before=t["fuel"], fuel_after=t["fuel"]); return
    choice_class = t['network'].get('choice_classes', {}).get(v) if t['current'] == t['network']['start'] else None
    fuel_before=t.get("fuel")
    if fuel_before is not None: t["fuel"] -= w
    t["last_move_from"] = t["current"]
    t["movement_started_at"] = time.time()
    t['current']=v; t['distance']+=w; t['moves']+=1
    refuelled = v in t['network'].get("fuel_stations", [])
    if refuelled: t["fuel"] = t["fuel_capacity"]
    log_event('move', moved_to=v, edge=k, edge_cost=w, choice_class=choice_class,
              fuel_before=fuel_before, fuel_after=t.get("fuel"), refuelled=str(refuelled))
    reveal_adjacent()
    if is_stranded():
        finish_stranded_trial()
        return True
    return False

def hindsight_route_svg(network, states, path):
    """A compact after-the-fact map with the realised shortest path highlighted."""
    chosen={edge_key(a,b) for a,b in zip(path,path[1:])}
    lines=[]
    for a,b,w,_ in network["edges"]:
        x1,y1=network["nodes"][a]; x2,y2=network["nodes"][b]; k=edge_key(a,b)
        if not states[k]: color="#dc2626"; dash="7,5"; width=3
        elif k in chosen: color="#16a34a"; dash=""; width=7
        else: color="#cbd5e1"; dash=""; width=3
        lines.append(f'<line x1="{x1*8}" y1="{y1*4}" x2="{x2*8}" y2="{y2*4}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/><text x="{(x1+x2)*4}" y="{(y1+y2)*2-4}" text-anchor="middle" font-size="12" fill="#334155">{w}</text>')
    nodes=[]
    for node,(x,y) in network["nodes"].items():
        fill="#2563eb" if node in (network["start"],network["goal"]) else "#fff"
        nodes.append(f'<circle cx="{x*8}" cy="{y*4}" r="14" fill="{fill}" stroke="#1e293b" stroke-width="2"/><text x="{x*8}" y="{y*4+5}" text-anchor="middle" font-size="13" font-weight="bold" fill="{"#fff" if fill=="#2563eb" else "#0f172a"}">{node}</text>')
    return '<svg viewBox="0 0 820 410" width="100%" style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px">'+''.join(lines+nodes)+'<g transform="translate(16,378)"><rect width="310" height="22" rx="6" fill="#fff"/><line x1="12" y1="11" x2="36" y2="11" stroke="#16a34a" stroke-width="6"/><text x="44" y="15" font-size="12">best fuel-feasible route</text><line x1="185" y1="11" x2="209" y2="11" stroke="#dc2626" stroke-width="3" stroke-dasharray="6,4"/><text x="217" y="15" font-size="12">blocked</text></g></svg>'

def set_trial_feedback(t, outcome):
    """Save debrief data without teaching subsequent levels by default."""
    feedback={
        "level":t["network"].get("level"), "network":t["network"]["name"], "outcome":outcome,
        "actual_distance":t["distance"], "optimum":t["optimum"],
        "path":t.get("optimum_path", []), "network_data":t["network"], "states":t["states"],
    }
    st.session_state.setdefault("debrief", []).append(feedback)
    # Between-level hindsight is deliberately opt-in: it is a learning manipulation.
    if SHOW_BETWEEN_LEVEL_HINDSIGHT and st.session_state.trial + 1 < len(NETWORKS):
        st.session_state.trial_feedback=feedback
    else:
        st.session_state.mission_notice=(
            "Mission complete — supplies reached the shelter." if outcome == "Delivered"
            else "Mission recorded — the truck could not continue from its final location."
        )

def finish_stranded_trial():
    """End an infeasible trial cleanly and preserve its event log for analysis."""
    t=st.session_state.t; elapsed=time.time()-t["start_time"]
    log_event("stranded", optimum_realized=t["optimum"], excess_distance=None, on_time=None)
    st.session_state.summary.append({"Trial":st.session_state.trial+1,"Network":t["network"]["name"],"Objective":t["objective"],"Outcome":"Stranded","Distance":t["distance"],"Fuel-feasible hindsight optimum":t["optimum"],"Excess distance":"—","Moves":t["moves"],"Decision time (s)":round(elapsed,1),"Deadline":str(t["deadline"]) if t["deadline"] is not None else "—","On time":"—","Surveillance used":t["surveillances_used"]})
    st.session_state.all_events.extend(t["events"])
    set_trial_feedback(t, "Stranded")
    st.session_state.trial+=1
    if st.session_state.trial<len(NETWORKS):
        initialise_trial()

def finish_trial():
    t=st.session_state.t; elapsed=time.time()-t['start_time']; on_time=(t['distance']<=t['deadline']) if t['objective']=='deadline' else None
    log_event('arrival', optimum_realized=t['optimum'], excess_distance=t['distance']-t['optimum'], on_time=on_time)
    st.session_state.summary.append({"Trial":st.session_state.trial+1,"Network":t['network']['name'],"Objective":t['objective'],"Outcome":"Delivered","Distance":t['distance'],"Fuel-feasible hindsight optimum":t['optimum'],"Excess distance":t['distance']-t['optimum'],"Moves":t['moves'],"Decision time (s)":round(elapsed,1),"Deadline":str(t['deadline']) if t['deadline'] is not None else "—","On time":str(on_time) if on_time is not None else "—",
                                     "Surveillance used":t["surveillances_used"]})
    st.session_state.all_events.extend(t['events'])
    set_trial_feedback(t, "Delivered")
    st.session_state.trial+=1
    if st.session_state.trial<len(NETWORKS): initialise_trial()

# Participant-facing introduction. It describes the task context without disclosing
# the study hypotheses, while retaining an explicit consent and privacy statement.
if 'started' not in st.session_state:
    st.title('Emergency relief dispatch')
    st.subheader('A community is waiting for supplies')
    st.write('A major storm has damaged roads across the region. You are part of the emergency coordination team. Your job is to guide one relief truck from the logistics depot at **A** to the community shelter at **B**, where people are waiting for food, water, and medical supplies.')
    st.subheader('Before you begin: what the map does and does not tell you')
    st.warning('**Road-status rule:** A gray road is not known to be open. Until the truck reaches either intersection at the end of that road, its actual status remains unknown—it may be passable or blocked. The gray label gives only its travel time and the *probability* that it is open. You learn the true status when the truck reaches either end, or earlier if you use a drone check.')
    st.info('You will complete **four short deliveries**. There is no specialist knowledge required and no single “right” way to approach every situation. Please make the choices that seem best to you.')
    st.markdown('''**What you will see**

- A road map showing travel times and the chance that an unrevealed road is passable.
- A truck icon showing the truck’s current location.
- In some deliveries, a fuel reserve and fuel depots.
- A small number of **drone checks**: dispatch a drone to inspect one road before the truck travels there.

Your choices and decision times are recorded without your name. Please do not enter a name or email as your participant code.''')
    st.divider()
    st.subheader('Before you begin')
    consent=st.checkbox('I am at least 18 and consent to anonymous data collection for this decision task.')
    pid=st.text_input('Participant code (optional; leave blank for a random anonymous code)')
    age=st.selectbox('Age band', ['Prefer not to say','18–24','25–34','35–44','45–54','55–64','65+'])
    gender=st.selectbox('Gender', ['Prefer not to say','Woman','Man','Non-binary','Self-describe'])
    if st.button('Read dispatch briefing', type='primary', disabled=not consent):
        st.session_state.started=True
        st.session_state.pid=pid.strip() or str(uuid.uuid4())
        st.session_state.demographics={'age_band':age,'gender':gender}
        st.session_state.practice=True
        st.rerun()
    st.stop()

if st.session_state.get('practice'):
    st.title('Dispatch briefing')
    st.write('Each map is a new emergency delivery. The truck starts at **A** and must reach the shelter at **B**. Roads are affected by the storm, so some are blocked.')
    c1,c2,c3=st.columns(3)
    c1.markdown("""**1. Read the map**

Each gray-road label shows `travel time | chance open` — for example, `2 | 80%`. Gray does **not** mean the road is open: its true status is still unknown. Only when the truck reaches either end of that road does it become green if passable or red if blocked.""")
    c2.markdown("""**2. Check roads when useful**

A gray road with a blue drone marker can be inspected from above. Click the road itself to send a drone check. The check does not move the truck or use travel time.""")
    c3.markdown("""**3. Keep moving safely**

Choose an adjacent road using the buttons beneath the map. In fuel deliveries, each road uses fuel equal to its travel time; green pump icons refill the truck.""")
    components.html(TUTORIAL_HTML, height=300, scrolling=False)
    st.caption('This is only an illustration: it does not reveal any of the four delivery maps or use a road-status check.')
    st.warning('Some deliveries ask you to minimise travel time. Others ask you to arrive before a travel-time limit. The map itself will clearly show the objective and your current status.')
    st.write('When you are ready, begin the first delivery. Take the decisions you would make if you were coordinating the relief truck.')
    if st.button('Begin first delivery', type='primary'):
        st.session_state.practice=False
        st.session_state.trial=0
        st.session_state.summary=[]
        st.session_state.all_events=[]
        st.session_state.debrief=[]
        st.session_state.mission_notice=None
        st.session_state.network_order=list(range(len(NETWORKS)))
        initialise_trial()
        st.rerun()
    st.stop()

if st.session_state.get("trial_feedback") and st.session_state.trial < len(NETWORKS):
    feedback=st.session_state.trial_feedback
    @st.dialog("Delivery recap")
    def delivery_recap_dialog():
        if feedback["outcome"] == "Stranded":
            st.error("The truck could not continue: no passable adjacent road could be travelled with the fuel remaining. This delivery has been recorded as stranded.")
        else:
            st.success("Supplies reached the shelter.")
        st.subheader("Best fuel-feasible route after the fact")
        st.write(f"Once all road closures are known, the shortest route that also respects the fuel limit is **{' → '.join(feedback['path'])}** (travel time **{feedback['optimum']}**).")
        st.write(f"Your delivery covered **{feedback['actual_distance']}** travel-time units.")
        st.markdown(hindsight_route_svg(feedback["network_data"], feedback["states"], feedback["path"]), unsafe_allow_html=True)
        st.caption("Green highlights the shortest fuel-feasible realised route; red dashed roads were blocked. This is hindsight feedback: it uses the complete realised road network, which was not available while you were making decisions.")
        if st.button("Continue to next delivery", type="primary"):
            st.session_state.trial_feedback=None
            st.rerun()
    delivery_recap_dialog()
    st.stop()

if st.session_state.trial>=len(NETWORKS):
    st.title('Finished')
    st.success("All four relief missions are complete.")
    st.markdown("""<div style="border:2px solid #f59e0b;border-radius:12px;padding:16px 20px;background:#fffbeb;margin:12px 0"><div style="font-size:22px;font-weight:700;color:#92400e">Emergency Dispatch Certificate</div><div style="color:#78350f">Four relief deliveries completed. Thank you for supporting the coordination exercise.</div></div>""", unsafe_allow_html=True)
    st.write("Your detailed route review is shown below only after the final level, so earlier feedback could not teach you how to approach later networks.")
    for item in st.session_state.get("debrief", []):
        with st.expander(f"Level {item['level']} hindsight review — {item['network']}", expanded=item['level']==4):
            if item['outcome'] == 'Stranded':
                st.error("The truck became stranded in this delivery.")
            else:
                st.success("Supplies reached the shelter.")
            st.write(f"With all road states known, the shortest route that also respects the fuel limit was **{' → '.join(item['path'])}** (travel time **{item['optimum']}**). Your truck covered **{item['actual_distance']}** time units.")
            st.markdown(hindsight_route_svg(item["network_data"], item["states"], item["path"]), unsafe_allow_html=True)
            st.caption("Green is the shortest fuel-feasible realised route; red dashed roads were blocked. This comparison uses information unavailable while you were routing.")
    st.write('The button below downloads your anonymous, analysis-ready event log. Events have also been saved locally as they occurred, including data from incomplete trials.')
    # The summary mixes numeric values with the em dash used for a stranded trial.
    # Render a display-only all-text copy so Arrow/PyArrow never receives a mixed column.
    display_summary=[{key: "—" if value is None else str(value) for key,value in row.items()}
                     for row in st.session_state.summary]
    st.dataframe(display_summary, hide_index=True, width="stretch")
    rows=[]
    for r in st.session_state.all_events: rows.append({**st.session_state.demographics,**r})
    out=io.StringIO(); writer=csv.DictWriter(out, fieldnames=sorted({k for r in rows for k in r})); writer.writeheader(); writer.writerows(rows)
    st.download_button('Download event log CSV',out.getvalue(),'uncertain_route_events.csv','text/csv')
    st.stop()

t=st.session_state.t; net=t['network']
notice=st.session_state.pop("mission_notice", None)
if notice:
    st.success(notice)
st.progress((st.session_state.trial) / len(NETWORKS), text=f"Mission progress: Level {st.session_state.trial+1} of {len(NETWORKS)}")
st.title(f"{net['name']} — relief delivery {st.session_state.trial+1} of {len(NETWORKS)}")
if net.get("level") == 4:
    st.warning("**Final challenge.** This is the most complex delivery: use the map, fuel depots, and drone checks deliberately. There is no time countdown; accuracy and routing judgement matter.")
st.write(net['description'])
if t['objective']=='speed': st.info('Objective: deliver supplies to B using as little **travel time** as possible. Make your route choice as quickly as you can.')
else: st.warning(f"Objective: deliver supplies to B before travel time **{t['deadline']}**. You are currently at travel time **{t['distance']}**. Make your route choice as quickly as you can.")
st.caption("Road-information rule: gray means the road’s actual status is unknown; its label shows travel time and chance open only. At either end, it is revealed as green (passable) or red dashed (blocked). Roads marked ‘checked’ were inspected by a drone.")
credits_left = t["surveillance_limit"] - t["surveillances_used"]
candidates = surveillance_candidates()
candidate_keys = {edge_key(a, b): (a, b) for a, b, _w, _p in candidates}
selected_edge = render_clickable_map(net, t, bool(candidates and credits_left > 0), credits_left)
# The browser component returns an edge only after an intentional direct click.
# Revalidate it server-side before spending a credit.
if selected_edge in candidate_keys and credits_left > 0:
    survey_edge(*candidate_keys[selected_edge])
    st.rerun()
if t["last_survey_result"] is not None:
    last = t["last_survey_result"]
    if last["open"]:
        st.success(f"Road-status update: {last['edge']} is passable. It is now green and marked ‘checked’ on the map.")
    else:
        st.error(f"Road-status update: {last['edge']} is blocked. It is now red and marked ‘checked’ on the map.")
if credits_left <= 0:
    st.caption("All road-status checks for this delivery have been used.")
elif not candidates:
    st.caption("There are no remaining unknown roads to check.")

st.write('Choose an adjacent road:')
cols=st.columns(max(1,len(neighbours())))
for col,(v,w) in zip(cols,neighbours()):
    k=edge_key(t['current'],v); label=f"Go to {v} ({w})"
    disabled=(k in t['revealed'] and not t['states'][k]) or (t.get("fuel") is not None and w > t["fuel"])
    if t.get("fuel") is not None and w > t["fuel"]:
        col.caption("Not enough fuel")
    if col.button(label, disabled=disabled, key=f"go-{t['current']}-{v}"):
        stranded = move(v,w)
        if stranded:
            st.rerun()
        if t['current']==net['goal']:
            finish_trial()
        st.rerun()
