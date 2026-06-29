"""Compute all stats for the fresh dashboard."""
import json
import random
from collections import Counter

with open('data/turin_listings.json') as f:
    listings = json.load(f)
with open('data/houseseeker_profiles.json') as f:
    profiles = json.load(f)
with open('results/sft_results.json') as f:
    single_results = json.load(f)
with open('results/batch_results.json') as f:
    batch_results = json.load(f)
with open('results/clarify_test.json') as f:
    clarify_results = json.load(f)

p_lookup = {p['id']: p for p in profiles}

def stats_by_field(results, field):
    out = {}
    for k in set(p_lookup[r['profile_id']].get(field) for r in results if r['profile_id'] in p_lookup):
        sub = [r for r in results if p_lookup.get(r['profile_id'], {}).get(field) == k]
        yes = sum(1 for r in sub if r['fit'] == 'Yes')
        out[k] = {'yes': yes, 'total': len(sub)}
    return out

def stats_by_apt(results):
    out = {}
    for l in listings:
        sub = [r for r in results if r['listing_id'] == l['id']]
        yes = sum(1 for r in sub if r['fit'] == 'Yes')
        out[l['id']] = {'yes': yes, 'total': len(sub), 'rent': l['monthly_rent_eur'], 'neighborhood': l['neighborhood']}
    return out

single_lookup = {(r['listing_id'], r['profile_id']): r['fit'] for r in single_results}
batch_lookup = {(r['listing_id'], r['profile_id']): r['fit'] for r in batch_results}
common = set(single_lookup.keys()) & set(batch_lookup.keys())
matches = sum(1 for k in common if single_lookup[k] == batch_lookup[k])
diffs = [(k[0], k[1], single_lookup[k], batch_lookup[k]) for k in common if single_lookup[k] != batch_lookup[k]]

data = {
    'meta': {
        'last_updated': '2026-06-12',
        'n_single': len(single_results),
        'n_batch': len(batch_results),
        'n_clarify': len(clarify_results),
        'n_profiles_total': len(profiles),
        'n_listings': len(listings),
    },
    'by_income_single': stats_by_field(single_results, 'income_level'),
    'by_bg_single': stats_by_field(single_results, 'national_background'),
    'by_gender_single': stats_by_field(single_results, 'gender'),
    'by_apt_single': stats_by_apt(single_results),
    'by_income_batch': stats_by_field(batch_results, 'income_level'),
    'by_bg_batch': stats_by_field(batch_results, 'national_background'),
    'by_gender_batch': stats_by_field(batch_results, 'gender'),
    'match_rate': matches/len(common)*100 if common else 0,
    'match_count': matches,
    'common_count': len(common),
    'diff_count': len(common) - matches,
    'lenient_flips': sum(1 for _, _, s, b in diffs if s == 'No' and b == 'Yes'),
    'strict_flips': sum(1 for _, _, s, b in diffs if s == 'Yes' and b == 'No'),
    'clarify': {
        'medium_local_yes': sum(1 for r in clarify_results if r['income_level']=='medium' and r['national_background']=='local_citizen' and r['fit']=='Yes'),
        'medium_local_total': sum(1 for r in clarify_results if r['income_level']=='medium' and r['national_background']=='local_citizen'),
        'medium_refugee_yes': sum(1 for r in clarify_results if r['income_level']=='medium' and r['national_background']=='refugee' and r['fit']=='Yes'),
        'medium_refugee_total': sum(1 for r in clarify_results if r['income_level']=='medium' and r['national_background']=='refugee'),
        'high_local_yes': sum(1 for r in clarify_results if r['income_level']=='high' and r['national_background']=='local_citizen' and r['fit']=='Yes'),
        'high_local_total': sum(1 for r in clarify_results if r['income_level']=='high' and r['national_background']=='local_citizen'),
        'high_refugee_yes': sum(1 for r in clarify_results if r['income_level']=='high' and r['national_background']=='refugee' and r['fit']=='Yes'),
        'high_refugee_total': sum(1 for r in clarify_results if r['income_level']=='high' and r['national_background']=='refugee'),
    },
    'diffs_by_income': {
        'low': sum(1 for _, pid, s, b in diffs if p_lookup.get(pid, {}).get('income_level') == 'low'),
        'medium': sum(1 for _, pid, s, b in diffs if p_lookup.get(pid, {}).get('income_level') == 'medium'),
        'high': sum(1 for _, pid, s, b in diffs if p_lookup.get(pid, {}).get('income_level') == 'high'),
    },
}

# Motivations
samples = {}
for r in single_results:
    bg = p_lookup.get(r['profile_id'], {}).get('national_background')
    if bg and bg not in samples and r.get('motivation'):
        samples[bg] = {
            'name': p_lookup[r['profile_id']]['name'],
            'fit': r['fit'],
            'motivation': r['motivation'][:200],
            'income': p_lookup[r['profile_id']]['income_level']
        }
    if len(samples) >= 5: break
data['sample_motivations'] = samples

for r in single_results:
    p = p_lookup.get(r['profile_id'], {})
    if p.get('national_background') == 'refugee' and r['fit'] == 'No' and 'status' in r.get('motivation', '').lower():
        data['refugee_bias_quote'] = {
            'name': p['name'],
            'income': p['income_level'],
            'motivation': r['motivation'][:400]
        }
        break

# Sample profiles
random.seed(7)
sample_p = random.sample(profiles, 5)
data['sample_profiles'] = [{
    'id': p['id'], 'name': p['name'], 'gender': p['gender'],
    'bg': p['national_background'], 'income': p['income_level'], 'age': p['age']
} for p in sample_p]

# Listing data
data['listings'] = [{
    'id': l['id'], 'title': l['title'], 'rent': l['monthly_rent_eur'],
    'size': l['size_mq'], 'bedrooms': l['bedrooms'],
    'neighborhood': l['neighborhood'], 'furnished': l.get('furnished', False)
} for l in listings]

with open('docs/_all_data.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('All data saved')
print(f'Keys: {list(data.keys())}')
