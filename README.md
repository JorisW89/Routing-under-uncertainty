# Uncertain-route experiment: Streamlit pilot

A browser-based task for studying route choice in a partially observable network. A participant drives a truck from A to B. Edge lengths are visible, but a road's open/closed state is revealed only after the truck reaches an adjacent node. The task implements the information structure of the Canadian Traveler Problem.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

For sharing, deploy the repository to Streamlit Community Cloud or another Streamlit host. The current prototype retains data only in the participant's browser session and exposes a participant CSV download at completion. It is therefore appropriate for usability testing and small pilots, not unattended multi-participant data collection.

## Design implemented

* **Six topology variants**, presented in participant-specific rotated order. They deliberately vary the decision structure: an early single-bridge gamble, choice among risky shortcuts, information gathering at a hub, a late irreversible gamble, redundant uncertain routes, and a multi-stage gamble with later exits.
* **Partial observability with known priors:** gray roads are unknown; their label states travel distance and the probability they are open. All edges adjacent to the current node become visible. Green roads are open; dashed red roads are blocked. This distinguishes informed risk-taking from guessing.
* **Two randomized objectives:** minimize travel distance (`speed`) or reach B within a pre-specified distance budget (`deadline`). The six-trial design gives each participant three trials of each objective. The deadline is a map-level constant, calculated from the all-open shortest route plus three distance units; it is not adjusted to the realized closures.
* **Guaranteed completion:** each map has one open route, so no participant is trapped. The guarantee is a design choice; for a later study, rotate the guaranteed route across participants to avoid systematically favoring one side of each map.
* **Minimal demographics:** age band and gender, both with a prefer-not-to-say option. The participant code is optional; blank generates an anonymous random code.

## Data produced

The final CSV is event-level: one record for every successful move, attempted closed edge, and final arrival. It contains participant code, trial, map, objective, timestamp, decision time since trial start, current node, cumulative distance, moves, and—for final arrivals—realized omniscient shortest distance, excess distance, and deadline success.

Suggested primary outcomes:

1. **Excess distance:** actual route distance minus the shortest route in the realized open/closed network. This measures the cost of decisions relative to full-information hindsight, but does not measure optimal behavior under partial information.
2. **Deadline success:** whether route distance was at or below the pre-specified deadline.
3. **Exploration/avoidance:** number of moves, attempted closed edges, first branch choice, and backtracking (derivable from the ordered move log).
4. **Decision time:** elapsed wall-clock seconds from trial onset; treat it separately from travel distance, since the stated task objective concerns route distance.

## Recommended study changes before inference by age or gender

* Add multiple independently generated maps per topology and randomize closure realizations, then use mixed-effects models with participant and map as random effects. Six trials per participant is adequate for a mechanics pilot, not subgroup inference.
* Counterbalance *which* route is guaranteed open and verify that closure probabilities and route geometry do not make one first move objectively dominant. Keep a versioned task-configuration file with a seed and all map parameters.
* Randomize objective within topology across the sample and pre-register the primary endpoint. Do not interpret sex/gender differences without a powered sampling plan; collect gender inclusively and separate it conceptually from sex if sex is required by the research question.
* Add comprehension checks after practice (e.g., "When is a road's status revealed?") and exclude only according to a pre-specified rule.
* Use a server-side database or study-platform integration; record consent version, study version, assignment, browser/device metadata only if approved, and a completion code. Obtain ethics/IRB approval and follow the applicable privacy rules before recruitment.

## Known pilot limitations

The visible maps are static and button-based, which improves auditability but is less immersive than a drag/click map. Edge closures are deterministic conditional on participant code and trial, allowing reproducibility; they are not cryptographically random. The app compares participants with an omniscient realized-network shortest path only after the trial; a normative partial-information benchmark (expected-cost policy) should be calculated offline for the final maps before claims about "human intuition" versus optimal CTP policies.
