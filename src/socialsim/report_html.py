"""Render a run report as one self-contained HTML page (no external assets, light and dark theme)."""
from __future__ import annotations

from datetime import datetime
from html import escape as _e
from typing import Any

ACTION_LABEL = {"convert": "Converteu", "click": "Clicou", "share": "Compartilhou", "comment": "Comentou",
                "like": "Curtiu", "ignore": "Ignorou", "reject": "Rejeitou"}
ACTION_CLASS = {"convert": "good", "share": "good", "click": "mid", "like": "mid", "comment": "mid",
                "ignore": "muted", "reject": "bad"}
SENTIMENT_LABEL = {"positive": "Positivo", "neutral": "Neutro", "negative": "Negativo"}

CSS = """
:root{--bg:#faf7f4;--card:#fff;--ink:#2a2420;--muted:#7a6f67;--line:#eadfd7;--accent:#d97757;
--good:#3b7d5c;--mid:#b9893b;--bad:#a8453d;--soft:#f6ece6}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1b1613;--card:#262019;--ink:#f3eae4;
--muted:#b3a59b;--line:#3a312a;--accent:#ee9272;--good:#6bbf94;--mid:#e0b25f;--bad:#e27d73;--soft:#30271f}}
:root[data-theme=dark]{--bg:#1b1613;--card:#262019;--ink:#f3eae4;--muted:#b3a59b;--line:#3a312a;--accent:#ee9272;
--good:#6bbf94;--mid:#e0b25f;--bad:#e27d73;--soft:#30271f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.55 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:0 16px 48px}
header{background:linear-gradient(135deg,#2d2420,#1f1a17);color:#faf3ee;padding:36px 0 40px;margin-bottom:28px}
header .wrap{padding-bottom:0}header h1{margin:6px 0 4px;font-size:30px;line-height:1.2}
header .kicker{color:#f0a98e;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12px}
header p{margin:0;color:#c9b8ad;font-size:14px}
h2{font-size:20px;margin:36px 0 12px;display:flex;align-items:center;gap:10px}
h2:before{content:"";width:6px;height:22px;border-radius:3px;background:var(--accent)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.kpi .v{font-size:32px;font-weight:700;line-height:1.1}.kpi .l{color:var(--muted);font-size:13px;margin-top:4px}
.verdict{font-size:18px;border-left:5px solid var(--accent)}
.row{display:grid;grid-template-columns:150px 1fr 54px;align-items:center;gap:10px;margin:8px 0;font-size:14px}
.bar{height:12px;border-radius:6px;background:var(--soft);overflow:hidden}.bar i{display:block;height:100%;border-radius:6px;background:var(--accent)}
.bar i.good{background:var(--good)}.bar i.mid{background:var(--mid)}.bar i.bad{background:var(--bad)}.bar i.muted{background:var(--muted)}
.row .n{text-align:right;color:var(--muted)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
.scroll{overflow-x:auto}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700;color:#fff;background:var(--muted)}
.pill.good{background:var(--good)}.pill.mid{background:var(--mid)}.pill.bad{background:var(--bad)}
.persona{display:flex;flex-direction:column;gap:8px}.persona .who{font-weight:700}.persona .meta{color:var(--muted);font-size:13px}
.quote{border-left:3px solid var(--line);padding-left:12px;font-style:italic}
.tags span{display:inline-block;background:var(--soft);border-radius:999px;padding:1px 9px;margin:2px 4px 2px 0;font-size:12px;color:var(--muted)}
ul.clean{margin:0;padding:0;list-style:none}ul.clean li{padding:10px 0 10px 30px;border-bottom:1px solid var(--line);position:relative}
ul.clean li:last-child{border-bottom:0}ul.clean li:before{content:"";position:absolute;left:4px;top:17px;width:12px;height:12px;border-radius:50%;background:var(--accent)}
ul.good li:before{background:var(--good)}ul.warn li:before{background:var(--bad)}
ol.steps{margin:0;padding-left:22px}ol.steps li{margin:6px 0}
.ad{background:var(--soft);border:1px dashed var(--accent);border-radius:12px;padding:14px 16px;font-size:17px}
.ad small{display:block;color:var(--muted);font-size:12px;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em}
.warnbox{border-left:5px solid var(--mid)}
footer{color:var(--muted);font-size:13px;margin-top:36px;text-align:center}
@media (max-width:560px){.row{grid-template-columns:110px 1fr 40px}header h1{font-size:24px}}
"""


def _pct(v: float | None) -> str:
    return "n/d" if v is None else f"{round(v * 100)}%"


def _num(v: float | None) -> str:
    return "n/d" if v is None else (str(int(v)) if float(v).is_integer() else f"{v:.1f}".replace(".", ","))


def _bars(items: list[tuple[str, int, str]], total: int) -> str:
    out = []
    for label, n, cls in items:
        w = 0 if not total else max(2 if n else 0, round(n / total * 100))
        out.append(f'<div class="row"><span>{_e(label)}</span><div class="bar"><i class="{cls}" style="width:{w}%"></i></div>'
                   f'<span class="n">{n}</span></div>')
    return "".join(out) or '<p class="meta">Sem dados.</p>'


def _list(items: list[str] | None, cls: str = "") -> str:
    if not items:
        return '<p class="meta">Nada informado.</p>'
    return f'<ul class="clean {cls}">' + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


def _section(title: str, body: str) -> str:
    return f"<h2>{_e(title)}</h2>{body}"


def render_html(report: dict[str, Any], idea: dict[str, Any], reactions: list[dict[str, Any]],
                analysis: dict[str, Any], research: list[dict[str, Any]] | None = None) -> str:
    """Build the page. Every dynamic string is escaped; numbers come from the report, text from `analysis`."""
    counts = report["counts"]
    ok = counts["ok"]
    title = analysis.get("title") or f"Relatório: {idea['name']}"
    run = report["run"]
    when = (run.get("finished_at") or run.get("started_at") or "")[:16].replace("T", " ")

    kpis = "".join(
        f'<div class="card kpi"><div class="v">{_e(v)}</div><div class="l">{_e(l)}</div></div>' for v, l in (
            (str(counts["planned"]), "personas simuladas"),
            (_pct(report["conversion_rate"]), "taxa de conversão"),
            (_pct(report["engagement_rate"]), "taxa de engajamento"),
            (f"{_num(report['avg_purchase_intent'])}/10", "intenção média de compra"),
            (str(counts["failed"]), "falhas")))

    action_items = [(ACTION_LABEL.get(a, a), n, ACTION_CLASS.get(a, "mid")) for a, n in
                    sorted(report["actions"].items(), key=lambda kv: -kv[1])]
    sent_items = [(SENTIMENT_LABEL.get(s, s), n, {"positive": "good", "neutral": "mid", "negative": "bad"}.get(s, "mid"))
                  for s, n in sorted(report["sentiment"].items(), key=lambda kv: -kv[1])]

    seg_rows = "".join(
        f"<tr><td>{_e(seg)}</td><td>{b['n']}</td>"
        f'<td><div class="bar"><i style="width:{round((b["avg_purchase_intent"] or 0) * 10)}%"></i></div></td>'
        f"<td>{_num(b['avg_purchase_intent'])}</td><td>{b['conversions']}</td><td>{b['positive']}</td><td>{b['negative']}</td></tr>"
        for seg, b in report["by_segment"].items())
    seg_table = ('<div class="card scroll"><table><tr><th>Segmento</th><th>N</th><th>Intenção</th><th></th>'
                 '<th>Conv.</th><th>Pos.</th><th>Neg.</th></tr>' + seg_rows + "</table></div>") if seg_rows else ""

    top_obj = report["top_objections"][:8]
    obj_total = max([o["count"] for o in top_obj], default=0)
    obj_html = _bars([(o["objection"], o["count"], "bad") for o in top_obj], obj_total)

    cards = []
    for r in sorted(reactions, key=lambda x: -(x["purchase_intent"] or 0)):
        cls = ACTION_CLASS.get(r["action"], "mid")
        quote = f'<div class="quote">“{_e(r["comment"])}”</div>' if r.get("comment") else ""
        objs = "".join(f"<span>{_e(o)}</span>" for o in (r.get("objections") or [])[:4])
        cards.append(
            f'<div class="card persona"><div class="who">{_e(r["name"])}, {r["age"]}</div>'
            f'<div class="meta">{_e(r.get("occupation") or "")} · {_e(r.get("segment") or "")}</div>'
            f'<div><span class="pill {cls}">{_e(ACTION_LABEL.get(r["action"], r["action"]))}</span> '
            f'<span class="meta">intenção {r["purchase_intent"]}/10 · {_e(SENTIMENT_LABEL.get(r["sentiment"], r["sentiment"]))}</span></div>'
            f'{quote}<div class="tags">{objs}</div></div>')

    ad = idea.get("ad_copy") or ""
    rewritten = analysis.get("rewritten_ad")
    ad_blocks = ""
    if ad:
        ad_blocks += f'<div class="ad"><small>Anúncio testado</small>{_e(ad)}</div>'
    if rewritten:
        ad_blocks += f'<div class="ad" style="margin-top:12px"><small>Sugestão de novo anúncio</small>{_e(rewritten)}</div>'

    parts = [
        f'<header><div class="wrap"><div class="kicker">social-sim · relatório de simulação</div><h1>{_e(title)}</h1>'
        f'<p>{_e(idea["name"])} · run {run["id"]} · {_e(when)}</p></div></header><div class="wrap">',
        f'<div class="kpis">{kpis}</div>',
    ]
    if analysis.get("verdict"):
        parts.append(_section("Veredito", f'<div class="card verdict">{_e(analysis["verdict"])}</div>'))
    if ad_blocks:
        parts.append(_section("O anúncio", ad_blocks))
    parts.append(_section("Como o público reagiu", f'<div class="grid2"><div class="card"><strong>Ações</strong>'
                          f'{_bars(action_items, ok)}</div><div class="card"><strong>Sentimento</strong>'
                          f'{_bars(sent_items, ok)}</div></div>'))
    if seg_table:
        parts.append(_section("Por segmento", seg_table))
    parts.append(_section("Principais objeções", f'<div class="card">{obj_html}</div>'))
    if cards:
        parts.append(_section("Cada persona", f'<div class="grid2">{"".join(cards)}</div>'))
    if analysis.get("strengths"):
        parts.append(_section("O que funcionou", f'<div class="card">{_list(analysis["strengths"], "good")}</div>'))
    if analysis.get("recommendations"):
        parts.append(_section("Recomendações para a ideia e o produto",
                              f'<div class="card">{_list(analysis["recommendations"])}</div>'))
    if analysis.get("ad_improvements"):
        parts.append(_section("Melhorias no anúncio", f'<div class="card">{_list(analysis["ad_improvements"])}</div>'))
    if analysis.get("risks"):
        parts.append(_section("Riscos", f'<div class="card">{_list(analysis["risks"], "warn")}</div>'))
    if analysis.get("next_steps"):
        steps = "".join(f"<li>{_e(s)}</li>" for s in analysis["next_steps"])
        parts.append(_section("Próximos passos", f'<div class="card"><ol class="steps">{steps}</ol></div>'))
    if research:
        rl = "".join(f"<li><strong>{_e(x['topic'])}:</strong> {_e(x['finding'])}</li>" for x in research)
        parts.append(_section("Pesquisa de mercado usada", f'<div class="card"><ul class="clean">{rl}</ul></div>'))
    caveats = analysis.get("caveats") or []
    base = ("Isto é uma simulação feita por um modelo de linguagem, não pesquisa de mercado. Tende a ser mais "
            "educada e mais razoável que gente real. Use para levantar objeções e hipóteses a testar com usuários "
            "de verdade, não como prova de demanda.")
    parts.append(_section("Ressalvas", f'<div class="card warnbox"><p style="margin-top:0">{_e(base)}</p>'
                          f'{_list(caveats, "warn") if caveats else ""}</div>'))
    parts.append(f'<footer>Gerado em {_e(datetime.now().strftime("%Y-%m-%d %H:%M"))} · idea {idea["id"]} · '
                 f'run {run["id"]} · social-sim</footer></div>')

    return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_e(title)}</title><style>{CSS}</style></head><body>{"".join(parts)}</body></html>')
