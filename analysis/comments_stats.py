import re, collections, json, csv
B = r'(?<![а-яёіўґєїa-z])'
L = open('data/comments_all.md', encoding='utf-8').read().split('\n')
rows, cur = [], None
for l in L:
    m = re.match(r'## (\d+)\. (.*)', l)
    if m: cur = (int(m[1]), m[2]); continue
    m = re.match(r'(\s*)- (↳ )?\*\*(.*?)\*\* \(👍 (\d+)\): (.*)', l)
    if m and cur:
        rows.append(dict(ep=cur[0], title=cur[1], reply=bool(m[2]), author=m[3], likes=int(m[4]), text=m[5]))
CAT = {
 'vitya':   B+r'(віц[яеюі]|віцьк|віт[яеюі]\b|вітьк|вит[яеюи]\b|витьк|віктар|виктор)',
 'timokh':  B+r'(цімох|тимох|тімох|акудовіч|акудович)',
 'cats':    B+r'(кот[ыаіуеи]?(?![а-яёіў])|котик|котік|котів|котам|котами|котов|котяр|коцік|коцiк|каты(?![а-яёіў])|катоў|катамі|катам(?![а-яёіў])|кошак|кошен|котяч|кацяня|мяў|мяу)',
 'graphics':B+r'(анімац|анимац|мульт|малюн|рисова|рисунк|ілюстрац|иллюстрац|візуал|визуал|карцінк|картинк|графік[аіуе]|графика|графіка|монтаж|мантаж|дызайн|дизайн|эфект|эффект|обладунк|касцюм|костюм|рэквізіт|реквизит)',
 'sound':   B+r'(музык|музыч|звук|гук[іу]|саундтр|мелод|агучк|агучв|озвуч|голас[аы]?\s+кат|голос[а]?\s+кот|змененым голасам|песн|пісн)',
 'humor':   B+r'(смешн|смяшн|сме[хю]|смяю|ржу|ржак|рагач|гумар|юмор|гумор|жарт|жартам|прыкол|прикол|😂|🤣)',
}
res = {}
for k, p in CAT.items():
    m = [r for r in rows if re.search(p, r['text'].lower())]
    res[k] = sorted(m, key=lambda r: -r['likes'])
top = sorted(rows, key=lambda r: -r['likes'])
authors = collections.Counter(r['author'] for r in rows)
ep_comments = collections.Counter(r['ep'] for r in rows)
def lang(t):
    t = t.lower()
    if re.search(r'[ўі]', t) and not re.search(r'[їєґ]', t): return 'be'
    if re.search(r'[їєґ]', t) or re.search(r'(?<![а-яёіў])(дякую|що|це|як же ми)(?![а-яёіў])', t): return 'uk'
    if re.search(r'[ыэъё]', t) or re.search(r'[а-я]', t): return 'ru'
    return 'other'
langs = collections.Counter(lang(r['text']) for r in rows if not r['reply'])
thanks = sum(bool(re.search(r'дзякуй|дякую|спасибо|благодар|dzięk', r['text'].lower())) for r in rows)
hearts = sum(r['text'].count('❤') + r['text'].count('♥') for r in rows)
out = dict(total=len(rows), top_level=sum(not r['reply'] for r in rows), replies=sum(r['reply'] for r in rows),
           unique_authors=len(authors), top_authors=authors.most_common(10),
           langs=dict(langs), thanks=thanks, hearts=hearts,
           most_commented=[(e, c) for e, c in ep_comments.most_common(5)],
           top=[{k: r[k] for k in ('ep','title','author','likes','text')} for r in top[:15]],
           cats={k: [{kk: r[kk] for kk in ('ep','title','author','likes','text')} for r in v] for k, v in res.items()},
           counts={k: len(v) for k, v in res.items()})
json.dump(out, open('analysis/comments_stats.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('total','top_level','replies','unique_authors','langs','thanks','hearts','counts','most_commented')}, ensure_ascii=False))
print(out['top_authors'])
