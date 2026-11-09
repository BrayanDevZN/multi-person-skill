"""report html: self-contained page, numbers from the database, text escaped, refuses partial runs."""
from __future__ import annotations


def _finish_run(seeded, tmp_path):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2, 3])
    seeded("reaction", "save", reactions=[
        {"run_id": 1, "persona_id": 1, "action": "convert", "sentiment": "positive", "purchase_intent": 9,
         "comment": "<b>quero</b>", "objections": ["price"]},
        {"run_id": 1, "persona_id": 2, "action": "reject", "sentiment": "negative", "purchase_intent": 1,
         "objections": ["price", "trust"]},
        {"run_id": 1, "persona_id": 3, "action": "ignore", "sentiment": "neutral", "purchase_intent": 2},
    ])
    seeded("run", "finish", "1")


def test_html_report_is_written_with_numbers_and_analysis(seeded, tmp_path):
    _finish_run(seeded, tmp_path)
    out = tmp_path / "r" / "run.html"
    res = seeded("report", "html", "1", "--out", str(out), verdict="Bom começo", recommendations=["Mostrar o preço"],
                 rewritten_ad="Novo anúncio", next_steps=["Rodar com 20 personas"])
    assert res.ok, res.error
    page = out.read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>") and "Bom começo" in page and "Mostrar o preço" in page
    assert "33%" in page  # 1 of 3 converted, straight from the database
    assert "Novo anúncio" in page and "Rodar com 20 personas" in page
    assert "<script" not in page and "http" not in page.replace("http-equiv", "")  # self-contained


def test_html_report_escapes_text(seeded, tmp_path):
    _finish_run(seeded, tmp_path)
    out = tmp_path / "run.html"
    assert seeded("report", "html", "1", "--out", str(out), verdict="<script>alert(1)</script>").ok
    page = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "<b>quero</b>" not in page and "&lt;b&gt;quero&lt;/b&gt;" in page


def test_html_report_refuses_pending_reactions(seeded, tmp_path):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2])
    res = seeded("report", "html", "1", "--out", str(tmp_path / "x.html"))
    assert not res.ok and "pending" in res.error


def test_html_report_rejects_unknown_fields_and_missing_run(seeded, tmp_path):
    _finish_run(seeded, tmp_path)
    assert not seeded("report", "html", "1", "--out", str(tmp_path / "x.html"), bogus="x").ok
    assert not seeded("report", "html", "99", "--out", str(tmp_path / "y.html")).ok
