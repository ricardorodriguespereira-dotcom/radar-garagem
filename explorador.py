#!/usr/bin/env python3
"""
Explorador de canais: encontra oportunidades para canais NOVOS, sem nicho fixo.

Sinal principal: canais com menos de 1 ano que já têm vídeos explodindo (muito mais views do que inscritos).
Se canais novos estão crescendo num assunto, o público está lá e ainda há espaço para entrar.

    python explorador.py              # coleta real (usa YOUTUBE_API_KEY, como o radar)
    python explorador.py --demo       # dados fictícios para testar
Opcional: ANTHROPIC_API_KEY faz o Claude agrupar os canais em ideias de canal, dizer se dá para fazer sem
aparecer e sugerir o ângulo para o Brasil.
Cota: ~2.500 unidades por rodada (o radar usa ~3.000; o limite diário é 10.000). Roda 1 vez por semana.
"""
import argparse, datetime as dt, html, json, math, os, re, statistics, sys, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import radar as RD

AQUI = Path(__file__).resolve().parent

CATEGORIAS = {"1": "Filmes e animação", "2": "Carros", "15": "Pets e animais", "17": "Esportes", "19": "Viagens",
              "20": "Games", "22": "Pessoas e blogs", "23": "Comédia", "24": "Entretenimento", "26": "Guias e estilo",
              "27": "Educação", "28": "Ciência e tecnologia", "10": "Música", "25": "Notícias e política",
              "29": "ONGs e ativismo"}
CAT_IGNORAR = {"10", "25"}  # música (gravadoras) e notícias (veículos) não viram oportunidade de canal novo

SEMENTES = {
    "US": ("en", ["explained", "how to", "facts you didn't know", "story", "documentary", "history of", "tutorial",
                  "top 10", "satisfying", "relaxing", "ai tools", "side hustle", "what happens if", "true story"]),
    "BR": ("pt", ["explicado", "como fazer", "curiosidades", "história", "documentário", "tutorial", "top 10",
                  "você sabia", "relaxante", "renda extra", "o que acontece se", "caso real"]),
}

STOP_PT = set("""o a os as um uma uns umas de do da dos das no na nos nas em por para pra com sem que e é ou se seu sua
seus suas meu minha mais menos muito como quando qual quais isso isto esse essa este esta foi ser são vai vou ao aos à
às já não sim nunca tudo todo toda todos todas ele ela eles elas eu você vocês nós ep parte""".split())
STOP_PT |= set("sobre entre até depois antes agora hoje aqui ali mesmo cada outro outra coisa coisas".split())
# palavras das próprias buscas não podem virar "tema"
PALAVRAS_SEMENTE = {w for _, (_, ss) in SEMENTES.items() for s in ss for w in s.lower().split()}
GENERICOS = set("""stories explained facts things people video videos shorts short viral trending trend fyp foryou foryoupage
for you edit edits meme memes funny funnyvideo comedy shortsfeed youtubeshorts youtubeshort ytshorts tiktok usa reels
explore explorepage new part official full hd love life story amazing best world mundo vídeo vídeos curiosidade
incrível incrivel humor engraçado engraçados""".split())
STOP = RD.STOP | STOP_PT | PALAVRAS_SEMENTE | GENERICOS


def amostra(yt, agora, dias):
    depois = (agora - dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids, origem = set(), {}
    for regiao in ("US", "BR"):
        for cat in CATEGORIAS:
            if cat in CAT_IGNORAR:
                continue
            for v in yt.populares(regiao, cat):
                ids.add(v); origem.setdefault(v, regiao)
        lang, seeds = SEMENTES[regiao]
        for s in seeds:
            print(f"{regiao}: buscando {s!r}", flush=True)
            for v in yt.buscar(s, regiao, lang, depois, n=50):
                ids.add(v); origem.setdefault(v, regiao)
    itens = yt.videos(sorted(ids))
    canais = {}
    cids = sorted({i["snippet"]["channelId"] for i in itens})
    for k in range(0, len(cids), 50):
        r = yt.get("channels", part="statistics,snippet", id=",".join(cids[k:k + 50]))
        for c in r.get("items", []):
            st = c.get("statistics", {})
            canais[c["id"]] = dict(
                nome=c["snippet"]["title"], criado=c["snippet"].get("publishedAt", ""),
                pais=c["snippet"].get("country", ""),
                inscritos=int(st.get("subscriberCount", 0) or 0), views=int(st.get("viewCount", 0) or 0),
                videos=int(st.get("videoCount", 0) or 0))
    return itens, canais, origem


PT_MARCAS = set("você voce não nao isso esse essa muito quando porque também tambem fazer como sobre está esta são sao uma pra seu sua do da dos das com ao pelo pela maior homem mulher".split())
ES_MARCAS = set("el los las una usted también porque está muy cuando cómo qué película completa historia real ella".split())
EN_MARCAS = set("the you this that with what why how your when they are for of and in to on is was ahead".split())
RISCO_REUSO = re.compile(r"full movie|filme completo|pel[ií]cula completa|movie explained|#edit|\bedits?\b|compilation|compila", re.I)


def idioma(titulo, declarado):
    if declarado[:2] in ("pt", "en", "es"):
        return declarado[:2]
    if re.search(r"[\u0900-\u0dff\u0600-\u06ff\u0e00-\u0fff\u3040-\u9fff\uac00-\ud7af]", titulo):
        return "outro"
    ws = set(re.findall(r"[a-zà-úç]+", titulo.lower()))
    pts, ess, ens = len(ws & PT_MARCAS), len(ws & ES_MARCAS), len(ws & EN_MARCAS)
    if re.search(r"[ãõç]", titulo.lower()):
        pts += 2
    if re.search(r"[ñ¿¡]", titulo.lower()):
        ess += 2
    m = max(pts, ess, ens)
    if m == 0:
        return "?"
    return "pt" if m == pts else ("es" if m == ess else "en")


def analisar(itens, canais, origem, agora, idade_max=365):
    por_canal = defaultdict(list)
    for v in itens:
        sn, st = v["snippet"], v.get("statistics", {})
        cid = sn["channelId"]
        if sn.get("categoryId") in CAT_IGNORAR or cid not in canais:
            continue
        views = int(st.get("viewCount", 0) or 0)
        idade = RD.idade_dias(sn["publishedAt"], agora)
        dur = RD.duracao_s(v.get("contentDetails", {}).get("duration"))
        por_canal[cid].append(dict(id=v["id"], titulo=sn["title"], views=views, vpd=views / idade, dur=dur,
                                   cat=sn.get("categoryId", ""), regiao=origem.get(v["id"], ""),
                                   idioma=(lambda l: l if l != "?" else ("pt" if origem.get(v["id"]) == "BR" else "en"))(
                                       idioma(sn["title"], (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or ""))),
                                   url=f"https://www.youtube.com/watch?v={v['id']}"))
    res = []
    for cid, vids in por_canal.items():
        c = canais[cid]
        if not c["criado"]:
            continue
        idade = RD.idade_dias(c["criado"], agora)
        melhor = max(vids, key=lambda x: x["vpd"])
        ins = max(c["inscritos"], 1000)
        outlier = melhor["views"] / ins
        media_canal = c["views"] / max(c["videos"], 1)
        novo = idade <= idade_max
        if not novo or melhor["views"] < 50_000:
            continue
        lingua = Counter(x["idioma"] for x in vids).most_common(1)[0][0]
        if lingua in ("outro", "es"):
            continue  # o explorador olha oportunidades em inglês (lá fora) e português (Brasil)
        shorts = sum(1 for x in vids if x["dur"] <= 180) / len(vids)
        reuso = any(RISCO_REUSO.search(x["titulo"]) for x in vids)
        score = math.log10(1 + melhor["vpd"]) * math.sqrt(min(outlier, 100)) * (1 + (idade_max - idade) / idade_max)
        res.append(dict(id=cid, nome=c["nome"], pais=c["pais"], idade=int(idade), inscritos=c["inscritos"],
                        videos=c["videos"], media=media_canal, outlier=outlier, melhor=melhor, vids=vids,
                        formato="Shorts" if shorts >= .5 else "Longo", score=score,
                        cat=Counter(x["cat"] for x in vids).most_common(1)[0][0],
                        regiao="BR" if lingua == "pt" else "EUA",
                        reuso=reuso,
                        url=f"https://www.youtube.com/channel/{cid}"))
    res.sort(key=lambda x: x["score"], reverse=True)
    return res


def grupos_heuristica(canais_novos, max_grupos=12):
    """Agrupa por categoria + expressões repetidas nos títulos dos canais novos."""
    termos = defaultdict(set)
    for c in canais_novos:
        vistos = set()
        for v in c["vids"]:
            toks = [t.lower() for t in re.findall(r"[^\W\d_][\w'\-]*", v["titulo"], re.UNICODE)]
            for n in (1, 2):
                for i in range(len(toks) - n + 1):
                    g = toks[i:i + n]
                    if any(t in STOP or len(t) < 3 for t in g):
                        continue
                    vistos.add(" ".join(g))
        for t in vistos:
            termos[t].add(c["id"])
    peso = {t: (1.6 if " " in t else 1.0) for t in termos}
    por_id = {c["id"]: c for c in canais_novos}
    cand = sorted(((sum(por_id[i]["score"] for i in ids) * peso[t], t, ids) for t, ids in termos.items()
                   if len(ids) >= 2 and (" " in t or len(t) >= 5)), reverse=True)
    grupos, usados = [], set()
    for s, t, ids in cand:
        ids = ids - usados if len(grupos) else ids
        if len(ids) < 2:
            continue
        membros = sorted((por_id[i] for i in ids), key=lambda c: c["score"], reverse=True)
        grupos.append(dict(tema=t, canais=membros, ideia="", sem_rosto=None, angulo_br=""))
        usados |= set(ids)
        if len(grupos) >= max_grupos:
            break
    # categoria como agrupamento de reserva
    por_cat = defaultdict(list)
    for c in canais_novos:
        if c["id"] not in usados:
            por_cat[c["cat"]].append(c)
    for cat, cs in sorted(por_cat.items(), key=lambda kv: -sum(c["score"] for c in kv[1])):
        if len(cs) >= 3 and len(grupos) < max_grupos + 2 and cat not in ("22", "24"):
            grupos.append(dict(tema=CATEGORIAS.get(cat, "Outros"), canais=cs, ideia="", sem_rosto=None, angulo_br=""))
    return grupos


def grupos_ia(canais_novos, chave, max_grupos=10):
    linhas = []
    for c in canais_novos[:80]:
        tits = " | ".join(v["titulo"] for v in sorted(c["vids"], key=lambda x: -x["vpd"])[:3])
        linhas.append(f'{c["id"]}\t{c["regiao"]}\t{c["formato"]}\t{c["idade"]}d\t{c["outlier"]:.0f}x\t{c["nome"]}: {tits}')
    prompt = f"""Você analisa oportunidades para abrir canais NOVOS no YouTube no Brasil, sem aparecer (faceless) de preferência.
Abaixo, canais com menos de 1 ano que estão explodindo (id, região da amostra, formato, idade, views do melhor vídeo ÷ inscritos, nome: títulos).
Agrupe-os em até {max_grupos} IDEIAS DE CANAL (um assunto + um formato), ignorando celebridades, música, notícias,
conteúdo infantil e qualquer coisa que dependa de pessoa famosa ou de reaproveitar vídeo alheio.
Responda SOMENTE com JSON: [{{"tema": "nome curto da ideia", "ideia": "1-2 frases do que o canal faria",
"sem_rosto": true|false, "angulo_br": "como adaptar ao público brasileiro e se já parece concorrido aqui",
"risco": "baixo|médio|alto (direitos autorais, política do YouTube, dependência de IA)", "ids": ["id", ...]}}]

""" + "\n".join(linhas)
    corpo = json.dumps(dict(model=os.environ.get("RADAR_MODELO", "claude-haiku-5-5"), max_tokens=5000,
                            messages=[dict(role="user", content=prompt)])).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=corpo, headers={
        "x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        texto = json.load(r)["content"][0]["text"]
    texto = texto[texto.find("["): texto.rfind("]") + 1]
    por_id = {c["id"]: c for c in canais_novos}
    out = []
    for g in json.loads(texto):
        cs = [por_id[i] for i in g.get("ids", []) if i in por_id]
        if cs:
            out.append(dict(tema=g.get("tema", ""), ideia=g.get("ideia", ""), sem_rosto=g.get("sem_rosto"),
                            angulo_br=g.get("angulo_br", ""), risco=g.get("risco", ""),
                            canais=sorted(cs, key=lambda c: -c["score"])))
    return out


def pontuar_grupos(grupos):
    for g in grupos:
        cs = g["canais"]
        g["n"] = len(cs)
        g["outlier_med"] = statistics.median(c["outlier"] for c in cs)
        g["idade_med"] = statistics.median(c["idade"] for c in cs)
        g["vpd"] = sum(c["melhor"]["vpd"] for c in cs)
        g["us"] = sum(1 for c in cs if c["regiao"] == "EUA")
        g["reuso"] = sum(1 for c in cs if c.get("reuso"))
        g["br"] = sum(1 for c in cs if c["regiao"] == "BR")
        g["formato"] = Counter(c["formato"] for c in cs).most_common(1)[0][0]
        lacuna = 1.3 if g["us"] and not g["br"] else 1.0  # explodindo lá fora e ainda sem canal novo aqui
        g["nota"] = round(math.log10(1 + g["vpd"]) * math.log2(1 + g["n"]) * math.sqrt(min(g["outlier_med"], 50)) * lacuna, 1)
    grupos.sort(key=lambda g: -g["nota"])
    return grupos


def fmt(n):
    return RD.fmt(n)


def salvar_html(grupos, canais_novos, caminho, info):
    esc = html.escape
    mx = max((g["nota"] for g in grupos), default=1) or 1
    blocos = []
    for i, g in enumerate(grupos, 1):
        lacuna = '<span class="tag ok">só lá fora: espaço no BR</span>' if g["us"] and not g["br"] else (
            '<span class="tag med">já tem canal novo no BR</span>' if g["br"] else "")
        rosto = "" if g["sem_rosto"] is None else (
            '<span class="tag ok">dá sem aparecer</span>' if g["sem_rosto"] else '<span class="tag sat">pede rosto</span>')
        reuso = '<span class="tag sat">canais reaproveitam conteúdo alheio: não copie o formato</span>' if g.get("reuso", 0) >= max(1, g["n"] / 2) else ""
        risco = f'<span class="tag {"sat" if g.get("risco") == "alto" else "med" if g.get("risco") == "médio" else "ok"}">risco {esc(g["risco"])}</span>' if g.get("risco") else ""
        cs = "".join(
            f'<li><a href="{esc(c["url"])}">{esc(c["nome"])}</a> <span>{c["idade"]} dias · {fmt(c["inscritos"])} inscritos · '
            f'{c["formato"]} · {c["regiao"]}</span><br><a class="v" href="{esc(c["melhor"]["url"])}">{esc(c["melhor"]["titulo"])}</a> '
            f'<span>{fmt(c["melhor"]["views"])} views ({c["outlier"]:.0f}× os inscritos)</span></li>' for c in g["canais"][:4])
        extra = "".join(f'<p class="ang"><b>{r}:</b> {esc(t)}</p>' for r, t in (("Ideia", g["ideia"]), ("Brasil", g["angulo_br"])) if t)
        blocos.append(f"""
<article><header><b>{i}</b><div><h2>{esc(g["tema"])}</h2>
<p class="tags">{lacuna}{rosto}{risco}{reuso}<span class="tag">{g["formato"]}</span></p></div></header>
<div class="bar"><i style="width:{100 * g["nota"] / mx:.0f}%"></i></div>{extra}
<dl><div><dt>Canais novos explodindo</dt><dd>{g["n"]}</dd></div><div><dt>Idade mediana</dt><dd>{g["idade_med"]:.0f} dias</dd></div>
<div><dt>Views ÷ inscritos (mediana)</dt><dd>{g["outlier_med"]:.0f}×</dd></div><div><dt>Views/dia somados</dt><dd>{fmt(g["vpd"])}</dd></div>
<div><dt>EUA / BR</dt><dd>{g["us"]} / {g["br"]}</dd></div></dl>
<h3>Canais de exemplo (para estudar, nunca copiar)</h3><ul>{cs}</ul></article>""")
    top = "".join(f'<tr><td><a href="{esc(c["url"])}">{esc(c["nome"])}</a></td><td>{c["regiao"]}</td><td>{c["idade"]}</td>'
                  f'<td>{fmt(c["inscritos"])}</td><td>{c["outlier"]:.0f}×</td><td>{c["formato"]}</td>'
                  f'<td>{esc(CATEGORIAS.get(c["cat"], c["cat"]))}</td></tr>' for c in canais_novos[:40])
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Explorador de canais</title><style>
:root{{--bg:#0a0f1e;--card:#131b32;--t:#ecf0f8;--m:#8794b2;--c:#3ac4ff;--a:#ffa826;--g:#48de84;--r:#ff6b6b;--l:#26304d}}
@media (prefers-color-scheme:light){{:root{{--bg:#f4f6fb;--card:#fff;--t:#111827;--m:#5b6478;--l:#dde2ee;--c:#0a84c6;--g:#147a44;--a:#b86e00;--r:#c62828}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--t);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:900px;margin:auto;padding:24px 16px 60px}}h1{{font-size:28px;margin:0 0 4px}}.info{{color:var(--m);margin:0 0 16px}}
.aviso{{border:1px solid var(--r);padding:10px 14px;border-radius:10px;margin-bottom:16px}}
article{{background:var(--card);border:1px solid var(--l);border-radius:16px;padding:18px;margin:14px 0}}
header{{display:flex;gap:14px;align-items:flex-start}}header b{{font-size:26px;color:var(--c);min-width:34px}}header div{{flex:1;min-width:0}}
h2{{margin:0;font-size:20px}}.tags{{margin:6px 0 0;display:flex;gap:6px;flex-wrap:wrap}}
.tag{{font-size:12px;font-weight:600;padding:3px 9px;border-radius:99px;background:var(--l);color:var(--m)}}
.ok{{color:var(--g)}}.med{{color:var(--a)}}.sat{{color:var(--r)}}
.bar{{height:6px;background:var(--l);border-radius:3px;margin:12px 0}}.bar i{{display:block;height:100%;background:var(--c);border-radius:3px}}
.ang{{margin:4px 0}}dl{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:10px 0}}
dl div{{background:var(--bg);border-radius:10px;padding:8px 10px}}dt{{color:var(--m);font-size:12px}}dd{{margin:0;font-weight:700;font-size:17px}}
h3{{font-size:13px;color:var(--m);margin:14px 0 4px;text-transform:uppercase;letter-spacing:.04em}}ul{{margin:0;padding-left:18px}}li{{margin:6px 0}}
a{{color:var(--c);text-decoration:none}}a.v{{color:var(--t)}}li span{{color:var(--m);font-size:13px}}
.tab{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--l);white-space:nowrap}}
</style></head><body><main>
<h1>Explorador de canais</h1>
<p class="info">{esc(info["quando"])} · vídeos dos últimos {info["dias"]} dias, EUA e Brasil · {info["n_canais"]} canais com menos de 1 ano explodindo · cota ≈ {info["cota"]}</p>
{'<p class="aviso">DADOS FICTÍCIOS (modo demo).</p>' if info["demo"] else ""}
<p class="info">Cada bloco é uma <b>ideia de canal</b>: um assunto em que canais NOVOS estão crescendo rápido. "Só lá fora" = explodindo nos EUA e ainda sem canal novo no Brasil na amostra. Os canais de exemplo servem para estudar o formato; o conteúdo do seu canal deve ser próprio.</p>
{"".join(blocos) or '<p class="info">Nenhum agrupamento nesta rodada.</p>'}
<h3>Todos os canais novos explodindo</h3>
<div class="tab"><table><tr><th>Canal</th><th>Região</th><th>Dias</th><th>Inscritos</th><th>Views÷insc.</th><th>Formato</th><th>Categoria</th></tr>{top}</table></div>
</main></body></html>"""
    Path(caminho).write_text(pagina, encoding="utf-8")


def demo(agora):
    import random
    rnd = random.Random(3)
    temas = [("AI history documentary", "US", "Longo"), ("satisfying restoration", "US", "Shorts"),
             ("curiosidades sobre o corpo humano", "BR", "Shorts"), ("true crime stories explained", "US", "Longo"),
             ("receitas rápidas de airfryer", "BR", "Shorts"), ("space facts explained", "US", "Shorts")]
    itens, canais, origem = [], {}, {}
    for k, (tema, reg, form) in enumerate(temas):
        for j in range(rnd.randint(2, 4)):
            cid = f"UCdemo{k}{j}"
            canais[cid] = dict(nome=f"[fictício] {tema.title()} {j + 1}", criado=(agora - dt.timedelta(days=rnd.randint(40, 330))).isoformat(),
                               pais="", inscritos=rnd.randint(2_000, 120_000), views=rnd.randint(1_000_000, 30_000_000), videos=rnd.randint(10, 90))
            for m in range(3):
                vid = f"demo{k}{j}{m}"
                origem[vid] = reg
                itens.append(dict(id=vid, snippet=dict(channelId=cid, title=f"{tema} #{m + 1}", categoryId="27",
                                                       publishedAt=(agora - dt.timedelta(days=rnd.randint(2, 30))).isoformat()),
                                  statistics=dict(viewCount=str(rnd.randint(80_000, 3_000_000))),
                                  contentDetails=dict(duration="PT45S" if form == "Shorts" else "PT11M")))
    return itens, canais, origem


def main():
    p = argparse.ArgumentParser(description="Explorador de oportunidades de canal (sem nicho)")
    p.add_argument("--dias", type=int, default=21)
    p.add_argument("--demo", action="store_true")
    p.add_argument("--sem-ia", action="store_true")
    a = p.parse_args()
    RD.carregar_env()
    agora = dt.datetime.now(dt.timezone.utc)
    cota = 0
    if a.demo:
        itens, canais, origem = demo(agora)
    else:
        chave = os.environ.get("YOUTUBE_API_KEY")
        if not chave:
            raise SystemExit("Defina YOUTUBE_API_KEY.")
        c = RD.Cota(); yt = RD.YouTube(chave, c)
        itens, canais, origem = amostra(yt, agora, a.dias)
        cota = c.usado
    novos = analisar(itens, canais, origem, agora)
    print(f"{len(novos)} canais novos explodindo.")
    grupos = None
    chave_ia = os.environ.get("ANTHROPIC_API_KEY")
    if chave_ia and not a.sem_ia and not a.demo and novos:
        try:
            grupos = grupos_ia(novos, chave_ia)
        except Exception as e:
            print(f"IA indisponível ({e}); usando agrupamento automático.")
    if not grupos:
        grupos = grupos_heuristica(novos)
    grupos = pontuar_grupos(grupos)
    pasta = AQUI / "explorador"; pasta.mkdir(exist_ok=True)
    nome = pasta / f"explorador_{agora.astimezone().strftime('%Y-%m-%d_%Hh%M')}.html"
    salvar_html(grupos, novos, nome, dict(quando=agora.astimezone().strftime("%d/%m/%Y %H:%M"), dias=a.dias,
                                          n_canais=len(novos), cota=cota, demo=a.demo))
    for i, g in enumerate(grupos[:10], 1):
        print(f"{i:>2}. {g['nota']:>5}  {g['tema']}  ({g['n']} canais, {g['formato']}, EUA {g['us']} / BR {g['br']})")
    print(f"\nRelatório: {nome}")


if __name__ == "__main__":
    main()
