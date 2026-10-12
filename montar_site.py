"""Monta o site do radar: a página inicial é sempre o relatório mais recente, com histórico."""
import html, re, shutil
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REL = AQUI / "relatorios"
SITE = AQUI / "site"


def nome_amigavel(p):
    m = re.match(r"radar_(\w+?)_(\d{4})-(\d{2})-(\d{2})_(\d{2})h(\d{2})", p.stem)
    if not m:
        return p.stem
    nicho, a, me, d, h, mi = m.groups()
    return f"{d}/{me}/{a} {h}:{mi} · {nicho}"


def barra(link, texto):
    return (f'<nav style="display:flex;justify-content:space-between;gap:12px;margin-bottom:16px;font-size:14px">'
            f'<span style="color:var(--m)">Garagem Técnica · radar</span>'
            f'<a href="{link}">{texto}</a></nav>')


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "relatorios").mkdir(parents=True)
    rels = sorted(REL.glob("radar_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    rels = sorted(rels, key=lambda p: p.name[-21:], reverse=True)  # ordena pela data no nome
    for p in rels:
        txt = p.read_text(encoding="utf-8").replace("<main>", "<main>" + barra("../historico.html", "Histórico"), 1)
        (SITE / "relatorios" / p.name).write_text(txt, encoding="utf-8")
    if rels:
        txt = rels[0].read_text(encoding="utf-8").replace("<main>", "<main>" + barra("historico.html", "Histórico"), 1)
    else:
        txt = "<!doctype html><meta charset=utf-8><p>Nenhum relatório ainda. Rode o workflow Radar.</p>"
    (SITE / "index.html").write_text(txt, encoding="utf-8")
    itens = "".join(f'<li><a href="relatorios/{html.escape(p.name)}">{html.escape(nome_amigavel(p))}</a></li>'
                    for p in rels)
    (SITE / "historico.html").write_text(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Histórico do radar</title>
<style>body{{margin:0;background:#0a0f1e;color:#ecf0f8;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:700px;margin:auto;padding:24px 16px}}a{{color:#3ac4ff;text-decoration:none}}li{{margin:8px 0}}
@media (prefers-color-scheme:light){{body{{background:#f4f6fb;color:#111827}}}}</style></head>
<body><main><p><a href="index.html">← Relatório mais recente</a></p><h1>Histórico</h1><ul>{itens}</ul></main></body></html>""",
                                         encoding="utf-8")
    print(f"site montado com {len(rels)} relatório(s)")


if __name__ == "__main__":
    main()
