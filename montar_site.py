"""Monta o site: radar (página inicial), explorador de canais e histórico dos dois."""
import html, re, shutil
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SITE = AQUI / "site"
FONTES = {"radar": (AQUI / "relatorios", "radar_*.html"), "explorador": (AQUI / "explorador", "explorador_*.html")}


def data_do_nome(p):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})h(\d{2})", p.stem)
    return "".join(m.groups()) if m else p.stem


def nome_amigavel(p):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})h(\d{2})", p.stem)
    if not m:
        return p.stem
    a, me, d, h, mi = m.groups()
    tipo = "Explorador de canais" if p.stem.startswith("explorador") else "Radar · " + p.stem.split("_")[1]
    return f"{d}/{me}/{a} {h}:{mi} · {tipo}"


def barra(prefixo, atual):
    links = [("index.html", "Radar"), ("explorador.html", "Explorador de canais"), ("historico.html", "Histórico")]
    itens = " · ".join(f'<b>{t}</b>' if h == atual else f'<a href="{prefixo}{h}">{t}</a>' for h, t in links)
    return (f'<nav style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px 12px;margin-bottom:16px;'
            f'font-size:14px"><span style="color:var(--m)">Garagem Técnica</span><span>{itens}</span></nav>')


def com_barra(p, prefixo, atual):
    return p.read_text(encoding="utf-8").replace("<main>", "<main>" + barra(prefixo, atual), 1)


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "relatorios").mkdir(parents=True)
    todos = []
    for chave, (pasta, padrao) in FONTES.items():
        rels = sorted(pasta.glob(padrao), key=data_do_nome, reverse=True) if pasta.exists() else []
        for p in rels:
            (SITE / "relatorios" / p.name).write_text(com_barra(p, "../", ""), encoding="utf-8")
        destino = "index.html" if chave == "radar" else "explorador.html"
        if rels:
            (SITE / destino).write_text(com_barra(rels[0], "", destino), encoding="utf-8")
        else:
            (SITE / destino).write_text(
                f'<!doctype html><meta charset=utf-8><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<p style="font:16px system-ui;padding:16px">Ainda não há relatório. Rode o workflow '
                f'"{"Radar" if chave == "radar" else "Explorador"}" em Actions.</p>', encoding="utf-8")
        todos += rels
    todos.sort(key=data_do_nome, reverse=True)
    itens = "".join(f'<li><a href="relatorios/{html.escape(p.name)}">{html.escape(nome_amigavel(p))}</a></li>' for p in todos)
    (SITE / "historico.html").write_text(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Histórico</title>
<style>body{{margin:0;background:#0a0f1e;color:#ecf0f8;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:700px;margin:auto;padding:24px 16px}}a{{color:#3ac4ff;text-decoration:none}}li{{margin:8px 0}}
@media (prefers-color-scheme:light){{body{{background:#f4f6fb;color:#111827}}a{{color:#0a84c6}}}}</style></head>
<body><main><p><a href="index.html">Radar</a> · <a href="explorador.html">Explorador de canais</a></p>
<h1>Histórico</h1><ul>{itens}</ul></main></body></html>""", encoding="utf-8")
    print(f"site montado com {len(todos)} relatório(s)")


if __name__ == "__main__":
    main()
