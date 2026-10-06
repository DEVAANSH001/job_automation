import json
from pathlib import Path
from jobbot.core import collect

valid = []
for slug in ['razorpay', 'mongodb', 'stripe']:
    board = {'source': 'greenhouse', 'slug': slug, 'company': slug.title()}
    try:
        count = len(list(collect(board)))
        print(slug, count)
        valid.append(board)
    except Exception as exc:
        print(slug, type(exc).__name__)
if valid:
    path = Path('config.json')
    cfg = json.loads(path.read_text())
    cfg['boards'] = valid
    path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
