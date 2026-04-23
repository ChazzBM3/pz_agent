import json
from pathlib import Path

summary_path = Path('/Users/chazzm3/.openclaw/workspace/pz_agent/artifacts/presentation_kg/top_phenothiazines_by_oxidation.json')
out_dir = Path('/Users/chazzm3/.openclaw/workspace/pz_agent/artifacts/presentation_kg')
rows = json.loads(summary_path.read_text())

# Simple presentation-friendly shortlist heuristic:
# prioritize high oxidation potential, but keep SA score visible as a practical filter.
ranked = []
for row in rows:
    ox = row.get('oxidation_potential')
    sa = row.get('sa_score')
    if ox is None:
        continue
    score = float(ox)
    if sa is not None:
        score -= 0.05 * max(float(sa) - 2.5, 0.0)
    ranked.append({
        **row,
        'presentation_priority_score': round(score, 4),
    })

ranked.sort(key=lambda x: (x['presentation_priority_score'], x['oxidation_potential'], x['id']), reverse=True)
shortlist = ranked[:5]

notes = {
    'heuristic': 'Rank by oxidation potential with a light SA-score penalty only for presentation-friendly prioritization, not as a production scientific objective.',
    'top5': shortlist,
    'talk_track': [
        'The KG already supports a practical phenothiazine shortlist without inventing a new model.',
        'A simple property-aware ranking is enough to surface a small high-redox, still-synthetically-plausible frontier.',
        'This is a good example of the KG acting as a scientific memory and prioritization substrate rather than only a storage layer.'
    ]
}

(out_dir / 'phenothiazine_priority_shortlist.json').write_text(json.dumps(shortlist, indent=2))
(out_dir / 'phenothiazine_priority_shortlist_notes.json').write_text(json.dumps(notes, indent=2))
print(json.dumps(notes, indent=2))
