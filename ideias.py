#!/usr/bin/env python3
"""
Ideias da semana do Garagem Técnica (substitui o radar diário).

Junta, uma vez por semana, ideias de fontes diferentes e mostra SÓ o que é novo:
  1. Dúvidas reais no Brasil: o que as pessoas digitam no YouTube e no Google (autocompletar), e se já existe
     vídeo bom em português respondendo (onde não existe = brecha).
  2. Lá fora, em 3 prazos: o que explodiu na semana, o que vai bem no mês e os clássicos do ano.
     Os países mudam toda semana (rodízio entre EUA, Reino Unido, Austrália, Canadá, Índia, México, Espanha,
     Argentina, Colômbia, Chile e Portugal).
  3. Dúvidas lá fora: o que motoristas dos EUA e do México digitam no YouTube e no Google.
  4. Calendário do Brasil nas próximas 6 semanas (feriados, chuva, calor, IPVA, Black Friday...).

    python ideias.py                 # coleta real (precisa da YOUTUBE_API_KEY)
    python ideias.py --demo          # dados fictícios, só para testar o relatório
    python ideias.py --paises US,MX,PT

Saída: ideias/ultimo.json, ideias/ideias_AAAA-MM-DD_HHhMM.html e ideias/historico.json (o que já apareceu).
Cota da YouTube API: ~3.500 unidades por rodada (de 10.000 por dia).
"""
import argparse, datetime as dt, html, json, os, random, re, sys, time, unicodedata
import urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

import radar as RD

AQUI = Path(__file__).resolve().parent
PASTA = AQUI / "ideias"

# ------------------------------------------------------------------ fontes
NOMES = {"US": "EUA", "GB": "Reino Unido", "AU": "Austrália", "CA": "Canadá", "IN": "Índia", "MX": "México",
         "ES": "Espanha", "AR": "Argentina", "CO": "Colômbia", "CL": "Chile", "PT": "Portugal"}
IDIOMA = {"US": "en", "GB": "en", "AU": "en", "CA": "en", "IN": "en", "MX": "es", "ES": "es", "AR": "es",
          "CO": "es", "CL": "es", "PT": "pt"}
# rodízio semanal: cada grupo mistura idiomas para variar o olhar
GRUPOS = [("US", "MX", "PT"), ("GB", "ES", "AU"), ("IN", "AR", "CA"), ("CO", "CL", "US"), ("AU", "MX", "GB")]
SEMENTES = {
    "en": ["car tips for beginners", "new driver mistakes", "car maintenance you can do yourself",
           "things your car is trying to tell you", "car myths busted", "how to check your car before a trip",
           "driving tips nobody tells you", "car features you didn't know", "car hacks that actually work",
           "why is my car making this noise", "first car buying tips", "car cleaning tips"],
    "es": ["consejos para conducir principiantes", "mantenimiento del auto tú mismo", "errores al manejar",
           "luces del tablero significado", "mitos de autos", "trucos para el auto",
           "funciones del auto que no conocías", "revisar el auto antes de viajar", "ruidos del auto"],
    "pt": ["dicas condução principiantes", "manutenção do carro", "erros ao conduzir", "luzes do painel",
           "mitos dos carros", "truques para o carro", "funções escondidas do carro", "revisão antes de viajar"],
}
JANELAS = [(7, "semana", "Explodindo nesta semana"), (30, "mes", "Fortes no último mês"),
           (365, "ano", "Clássicos do ano (provados)")]
PERGUNTAS = ["como saber se o carro", "por que o carro", "o que fazer quando o carro", "é normal o carro",
             "posso dirigir com", "o que significa a luz", "qual a diferença entre", "como funciona o",
             "quanto custa trocar", "carro fazendo barulho", "vale a pena carro", "pode lavar",
             "como economizar", "primeira vez dirigindo"]
EXPANDIR = ["como saber se o carro", "por que o carro", "o que fazer quando o carro", "é normal o carro"]
LETRAS = "abcdefghijlmnopqrstuv"
PERGUNTAS_FORA = {
    ("en", "us"): ["why does my car", "is it normal for my car", "what happens if you", "how do i know if my car",
                   "can i drive with", "what does it mean when your car", "should i warm up my car", "how often should i"],
    ("es", "mx"): ["por qué mi carro", "por qué mi auto", "es normal que mi carro", "qué pasa si mi carro",
                   "cómo saber si mi carro", "se puede manejar con", "cada cuánto se cambia"],
}
BANDEIRA = {"us": "EUA", "mx": "México"}
UA = {"User-Agent": "garagem-tecnica-ideias/1.0 (canal educativo)"}


# ------------------------------------------------------------------ utilidades
def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def latino(s):
    letras = [c for c in s if c.isalpha()]
    return not letras or sum(c.isascii() or c in "áàâãéêíóôõúçñüÁÀÂÃÉÊÍÓÔÕÚÇÑÜ¿¡" for c in letras) / len(letras) > .9


MARCAS_EXTRA = set("""maruti suzuki tata mahindra nexon brezza venue creta swift kwid onix hb20 gol polo cavalier camry
rav4 f150 tacoma silverado wrangler mustang tracker hrv crv kicks sentra versa yaris etios strada toro""".split())
CARRO = set("""car cars carro carros auto autos coche coches vehiculo vehiculos vehicle vehicles veiculo veiculos motor
engine oil aceite oleo brake brakes freno frenos freio freios tire tires tyre tyres llanta llantas neumatico neumaticos
pneu pneus battery bateria driving drive driver drivers manejar conducir conduccion dirigir mechanic mecanico dashboard
tablero painel headlight headlights faros farol faroles wiper wipers limpiaparabrisas parabrisas windshield radiator
radiador coolant transmission embrague embreagem clutch gasolina fuel combustible combustivel suv truck camioneta
parking estacionar taller oficina mecanica volante steering exhaust escape""".split())
FORA = set("""gta game games gameplay roblox minecraft simulator 3d prank challenge filter meme memes asmr reaction
funny tiktok song music trailer movie free fire mestre menu craft brush ff""".split())


def tem_marca(titulo):
    return any(p in RD.MARCAS or p in MARCAS_EXTRA for p in norm(titulo).split())


def relevante(titulo):
    ps = set(norm(titulo).split())
    return bool(ps & CARRO) and not (ps & FORA) and not ({"vs", "versus"} & ps)


def get_json(url, tentativas=2):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            erro = e
            time.sleep(1.5 * (i + 1))
    raise erro


def semana_iso(hoje):
    return hoje.isocalendar()[1]


# ------------------------------------------------------------------ 1. dúvidas reais no Brasil
def autocompletar(q, youtube=True):
    p = dict(client="firefox", hl="pt-BR", gl="br", q=q)
    if youtube:
        p["ds"] = "yt"
    try:
        d = get_json("https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(p), 1)
        return d[1] if len(d) > 1 else []
    except Exception:
        return None


FIM_RUIM = set("o a os as de do da dos das com que quando se e no na um uma para pra por em meu minha".split())


def incompleta(s):
    n = norm(s)
    return n.split()[-1] in FIM_RUIM or bool(re.search(r"(quando|se|que|porque|por que) (o|meu|a|seu) carro$", n))


def duvidas_br():
    consultas = list(PERGUNTAS) + [f"{e} {l}" for e in EXPANDIR for l in LETRAS]
    pontos, fonte, falhas = defaultdict(float), defaultdict(set), 0
    for q in consultas:
        for yt in (True, False):
            sug = autocompletar(q, yt)
            if sug is None:
                falhas += 1
                continue
            for pos, s in enumerate(sug[:10]):
                s = s.strip()
                if len(s.split()) < 4 or norm(s) == norm(q) or incompleta(s):
                    continue
                pontos[s] += 1 + (10 - pos) / 10
                fonte[s].add("YouTube" if yt else "Google")
            time.sleep(.15)
    # junta variações quase iguais (mesmas palavras)
    uniq = {}
    for s, p in sorted(pontos.items(), key=lambda x: -x[1]):
        k = " ".join(sorted(set(norm(s).split())))
        if k in uniq:
            uniq[k]["pontos"] += p
            uniq[k]["fontes"] |= fonte[s]
        else:
            uniq[k] = dict(texto=s, pontos=p, fontes=set(fonte[s]))
    out = sorted(uniq.values(), key=lambda x: -x["pontos"])
    for o in out:
        o["fontes"] = sorted(o["fontes"])
        o["pontos"] = round(o["pontos"], 1)
    return out, falhas, len(consultas) * 2


def medir_oferta(yt, duvidas, agora, n):
    """Para as n primeiras dúvidas: o melhor vídeo em português dos últimos 2 anos (100 unidades cada)."""
    depois = (agora - dt.timedelta(days=730)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for d in duvidas[:n]:
        try:
            ids = yt.buscar(d["texto"], "BR", "pt", depois, n=10)
            vids = yt.videos(ids) if ids else []
        except SystemExit as e:
            d["oferta"] = None
            print("  oferta: parou na cota:", e, file=sys.stderr)
            break
        melhor = max((int(v.get("statistics", {}).get("viewCount", 0) or 0) for v in vids), default=0)
        d["oferta"] = dict(videos=len(vids), melhor_views=melhor)
        d["brecha"] = len(vids) < 5 or melhor < 50_000


# ------------------------------------------------------------------ 2. lá fora, em 3 prazos
def la_fora(yt, paises, sementes_semana, agora):
    achados = {}
    for pais in paises:
        lang = IDIOMA[pais]
        for semente in sementes_semana[lang]:
            for dias, chave, _ in JANELAS:
                depois = (agora - dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
                try:
                    ids = yt.buscar(semente, pais, lang, depois, n=15)
                except SystemExit as e:
                    print("  busca parou:", e, file=sys.stderr)
                    return achados
                for i in ids:
                    a = achados.setdefault(i, dict(paises=set(), janelas=set(), sementes=set()))
                    a["paises"].add(pais); a["janelas"].add(chave); a["sementes"].add(semente)
    return achados


def montar_la_fora(yt, achados, agora):
    if not achados:
        return []
    itens = yt.videos(list(achados))
    canais = yt.canais(list({v["snippet"]["channelId"] for v in itens}))
    vids = RD.enriquecer(itens, canais, agora)
    out = []
    for v in vids:
        a = achados[v["id"]]
        if not latino(v["titulo"]) or tem_marca(v["titulo"]) or not relevante(v["titulo"]) or v["views"] < 5_000:
            continue
        v.update(paises=sorted(a["paises"]), janelas=sorted(a["janelas"]), sementes=sorted(a["sementes"]))
        out.append(v)
    return out


def separar_prazos(vids, por_janela=12):
    res = {}
    usados = set()
    for dias, chave, _ in JANELAS:
        cand = [v for v in vids if v["idade"] <= dias + 1 and v["id"] not in usados]
        if chave == "semana":
            cand.sort(key=lambda v: -v["vpd"])
        elif chave == "mes":
            cand.sort(key=lambda v: -(min(v["outlier"], 50) * (v["views"] ** .5)))
        else:
            cand = [v for v in cand if v["outlier"] >= 1.5 or v["views"] >= 1_000_000]
            cand.sort(key=lambda v: -v["views"])
        res[chave] = cand[:por_janela]
        usados |= {v["id"] for v in res[chave]}
    return res


# ------------------------------------------------------------------ 3. dúvidas lá fora
def duvidas_fora():
    out, falhas, total = [], 0, 0
    for (hl, gl), stems in PERGUNTAS_FORA.items():
        pontos = defaultdict(float)
        for q in stems:
            for yt in (True, False):
                p = dict(client="firefox", hl=hl, gl=gl, q=q)
                if yt:
                    p["ds"] = "yt"
                total += 1
                try:
                    d = get_json("https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(p), 1)
                    sug = d[1] if len(d) > 1 else []
                except Exception:
                    falhas += 1
                    continue
                for pos, t in enumerate(sug[:10]):
                    ruim = {"the", "a", "my", "to", "of", "el", "la", "mi", "de", "que", "con", "un", "una"}
                    if len(t.split()) >= 5 and not tem_marca(t) and norm(t).split()[-1] not in ruim:
                        pontos[t.strip()] += 1 + (10 - pos) / 10
                time.sleep(.15)
        for t, pt in sorted(pontos.items(), key=lambda x: -x[1])[:15]:
            out.append(dict(id=f"{gl}:{norm(t)}", pais=BANDEIRA[gl], texto=t, pontos=round(pt, 1)))
    return out, falhas, total


# ------------------------------------------------------------------ 4. calendário do Brasil
def pascoa(ano):
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(ano, mes, dia)


def eventos_ano(ano):
    P = pascoa(ano)
    bf = max(dt.date(ano, 11, d) for d in range(22, 31) if dt.date(ano, 11, d).weekday() == 4)
    E = [
        (dt.date(ano, 1, 2), dt.date(ano, 3, 31), "IPVA e licenciamento", "como pagar, desconto à vista, multa por atraso, documento digital"),
        (dt.date(ano, 1, 1), dt.date(ano, 3, 15), "Chuvas fortes (Sudeste e Centro-Oeste)", "aquaplanagem, rua alagada, palheta, desembaçar"),
        (dt.date(ano, 1, 15), dt.date(ano, 2, 15), "Volta às aulas", "cadeirinha, transporte de crianças, trânsito na porta da escola"),
        (P - dt.timedelta(days=50), P - dt.timedelta(days=46), "Carnaval", "viagem, lei seca, carro cheio, calibragem com peso"),
        (P - dt.timedelta(days=4), P, "Feriado de Páscoa", "checklist de viagem, estrada, cansaço ao volante"),
        (dt.date(ano, 4, 18), dt.date(ano, 4, 21), "Tiradentes", "viagem curta, estrada"),
        (dt.date(ano, 5, 1), dt.date(ano, 5, 31), "Maio Amarelo (segurança no trânsito)", "série Por que é perigoso? em alta"),
        (P + dt.timedelta(days=58), P + dt.timedelta(days=61), "Corpus Christi", "feriado prolongado, estrada"),
        (dt.date(ano, 6, 1), dt.date(ano, 8, 31), "Frio e inverno", "bateria fraca, neblina, desembaçar, motor frio (mito de esquentar)"),
        (dt.date(ano, 7, 1), dt.date(ano, 7, 31), "Férias de julho", "viagem com crianças, checklist, estepe"),
        (dt.date(ano, 7, 25), dt.date(ano, 7, 25), "Dia do Motorista", "homenagem, curiosidades"),
        (dt.date(ano, 8, 1), dt.date(ano, 10, 15), "Tempo seco e queimadas", "fumaça na estrada, visibilidade, filtro de cabine, ar seco"),
        (dt.date(ano, 9, 18), dt.date(ano, 9, 25), "Semana Nacional de Trânsito", "regras do CTB, multas, segurança"),
        (dt.date(ano, 9, 22), dt.date(ano, 12, 20), "Calor (primavera/verão)", "ar-condicionado, carro no sol, superaquecimento, água do radiador"),
        (dt.date(ano, 10, 1), dt.date(ano, 12, 31), "Começo das chuvas", "aquaplanagem, palheta, rua alagada, faróis"),
        (dt.date(ano, 10, 12), dt.date(ano, 10, 12), "Dia das Crianças", "segurança de crianças no carro"),
        (dt.date(ano, 10, 30), dt.date(ano, 11, 2), "Finados", "feriado prolongado, viagem"),
        (dt.date(ano, 11, 13), dt.date(ano, 11, 15), "Proclamação da República", "feriado, estrada"),
        (dt.date(ano, 11, 20), dt.date(ano, 11, 20), "Consciência Negra (feriado nacional)", "feriado, viagem curta"),
        (bf - dt.timedelta(days=10), bf + dt.timedelta(days=3), "Black Friday", "comprar carro, pneu, acessórios: golpes e o que vale a pena"),
        (dt.date(ano, 12, 15), dt.date(ano, 12, 31), "Natal, Ano Novo e férias", "viagem longa, checklist, cansaço, lei seca, IPVA chegando"),
    ]
    return E


def calendario(hoje, dias=42):
    fim = hoje + dt.timedelta(days=dias)
    out = []
    for ano in (hoje.year, hoje.year + 1):
        for ini, fi, nome, ideia in eventos_ano(ano):
            if ini <= fim and fi >= hoje:
                out.append(dict(inicio=ini.isoformat(), fim=fi.isoformat(), evento=nome, ideias=ideia,
                                ja_comecou=ini <= hoje))
    out.sort(key=lambda e: e["inicio"])
    return out


# ------------------------------------------------------------------ histórico (só o que é novo)
def carregar_hist():
    p = PASTA / "historico.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def filtrar_novos(lista, chave, hist, tipo, hoje, dias=56):
    vistos = hist.setdefault(tipo, {})
    out = []
    for x in lista:
        k = chave(x)
        quando = vistos.get(k)
        if quando and (hoje - dt.date.fromisoformat(quando)).days <= dias:
            continue
        out.append(x)
    return out


def registrar(lista, chave, hist, tipo, hoje):
    for x in lista:
        hist.setdefault(tipo, {}).setdefault(chave(x), hoje.isoformat())


# ------------------------------------------------------------------ relatório
CSS = """:root{--bg:#0a0f1e;--p:#141b2e;--t:#ecf0f8;--m:#9aa6bf;--a:#ffb020;--c:#3ac4ff;--g:#3ddc84;--r:#ff5a5f;--v:#a082ff}
@media (prefers-color-scheme:light){:root{--bg:#f4f6fb;--p:#fff;--t:#111827;--m:#5b6475;--a:#b36b00;--c:#0a84c6;--g:#17803d;--r:#c0262d;--v:#6a4cd6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:860px;margin:auto;padding:20px 16px 60px}h1{font-size:24px;margin:4px 0}h2{font-size:18px;margin:28px 0 4px}
.sub{color:var(--m);margin:0 0 10px;font-size:14px}a{color:var(--c);text-decoration:none}
ol{padding-left:22px;margin:6px 0}li{margin:8px 0}.meta{color:var(--m);font-size:13px}
.tag{display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:9px;margin-right:4px;vertical-align:1px}
.novo{background:var(--g);color:#06210f}.brecha{background:var(--a);color:#2a1a00}.pais{border:1px solid var(--m);color:var(--m)}
.card{background:var(--p);border-radius:14px;padding:12px 14px;margin:8px 0}.aviso{color:var(--m);font-style:italic}"""


def fmt(n):
    return RD.fmt(n) if hasattr(RD, "fmt") else f"{n:,}".replace(",", ".")


def html_relatorio(d):
    e = html.escape
    p = []
    p.append(f"<h1>Ideias da semana</h1><p class=sub>{e(d['gerado_legivel'])} · países desta semana: "
             f"{e(', '.join(NOMES[x] for x in d['paises']))} · mostra só o que não apareceu nas últimas 8 semanas</p>")
    p.append("<h2>1. Dúvidas reais no Brasil</h2><p class=sub>O que as pessoas digitam no YouTube e no Google. "
             "<span class='tag brecha'>BRECHA</span> = pouco vídeo bom em português respondendo.</p><ol>")
    for x in d["duvidas"][:30]:
        tags = "<span class='tag brecha'>BRECHA</span>" if x.get("brecha") else ""
        of = x.get("oferta")
        meta = f"aparece no {' e '.join(x['fontes'])}"
        if of:
            meta += f" · melhor vídeo BR: {fmt(of['melhor_views'])} views"
        p.append(f"<li>{tags}{e(x['texto'])}<div class=meta>{meta}</div></li>")
    if not d["duvidas"]:
        p.append(f"<li class=aviso>{e(d['avisos'].get('duvidas', 'sem dúvidas novas nesta semana'))}</li>")
    p.append("</ol>")
    for dias, chave, titulo in JANELAS:
        p.append(f"<h2>2. Lá fora · {e(titulo)}</h2><p class=sub>Vídeos publicados nos últimos {dias} dias, "
                 f"ignorando marcas e modelos.</p><ol>")
        lst = d["la_fora"].get(chave, [])
        for v in lst:
            ps = " ".join(f"<span class='tag pais'>{e(NOMES[x])}</span>" for x in v["paises"])
            tipo = "Short" if v["short"] else f"{v['duracao'] // 60} min"
            p.append(f"<li>{ps}<a href='{e(v['url'])}' target=_blank>{e(v['titulo'])}</a><div class=meta>"
                     f"{fmt(v['views'])} views · {fmt(int(v['vpd']))}/dia · canal com {fmt(v['inscritos'])} inscritos "
                     f"(×{v['outlier']:.1f}) · {tipo}</div></li>")
        if not lst:
            p.append("<li class=aviso>nada novo neste prazo</li>")
        p.append("</ol>")
    p.append("<h2>3. Dúvidas lá fora</h2><p class=sub>O que motoristas dos EUA e do México digitam no YouTube e "
             "no Google. Se a dúvida também existe aqui, vira vídeo.</p><ol>")
    for r in d["duvidas_fora"][:24]:
        p.append(f"<li><span class='tag pais'>{e(r['pais'])}</span>{e(r['texto'])}</li>")
    if not d["duvidas_fora"]:
        p.append(f"<li class=aviso>{e(d['avisos'].get('fora', 'nada novo nesta semana'))}</li>")
    p.append("</ol><h2>4. Calendário: próximas 6 semanas</h2><p class=sub>Ganchos de época para encaixar na pauta.</p>")
    for c in d["calendario"]:
        ini = dt.date.fromisoformat(c["inicio"]).strftime("%d/%m")
        fim = dt.date.fromisoformat(c["fim"]).strftime("%d/%m")
        quando = ("até " + fim if c["ja_comecou"] else (ini if ini == fim else f"{ini} a {fim}"))
        p.append(f"<div class=card><b>{e(c['evento'])}</b> <span class=meta>· {e(quando)}</span>"
                 f"<div class=meta>{e(c['ideias'])}</div></div>")
    if d["avisos"]:
        p.append("<h2>Avisos</h2><ul>" + "".join(f"<li class=meta>{e(v)}</li>" for v in d["avisos"].values()) + "</ul>")
    return (f"<!doctype html><html lang=pt-BR><head><meta charset=utf-8><meta name=viewport "
            f"content='width=device-width,initial-scale=1'><title>Ideias da semana</title><style>{CSS}</style></head>"
            f"<body><main>{''.join(p)}</main></body></html>")


# ------------------------------------------------------------------ demo
def demo(agora):
    random.seed(3)
    duv = [dict(texto=t, pontos=random.randint(3, 20), fontes=["YouTube", "Google"],
                oferta=dict(videos=random.randint(1, 10), melhor_views=random.randint(5_000, 900_000)))
           for t in ["como saber se o carro está com problema na embreagem", "por que o carro treme quando liga o ar",
                     "o que fazer quando o carro morre no trânsito", "é normal o carro fazer barulho ao virar o volante",
                     "posso dirigir com a luz do óleo acesa", "qual a diferença entre óleo sintético e mineral"]]
    for x in duv:
        x["brecha"] = x["oferta"]["videos"] < 5 or x["oferta"]["melhor_views"] < 50_000
    def v(i, t, pais, idade, views, insc, dur):
        return dict(id=f"demo{i}", titulo=t, canal="Canal", views=views, idade=idade, vpd=views / idade, inscritos=insc,
                    outlier=views / max(insc, 1000), duracao=dur, short=dur <= 180, url="https://www.youtube.com",
                    paises=[pais], janelas=[], sementes=[])
    vids = [v(1, "I tried every car hack on TikTok", "US", 4, 900_000, 40_000, 50),
            v(2, "Errores que todos cometen al estacionar", "MX", 6, 300_000, 9_000, 40),
            v(3, "Why your car smells like rotten eggs", "GB", 20, 1_200_000, 200_000, 600),
            v(4, "Truques do porta-bagagens que ninguém conhece", "PT", 25, 80_000, 3_000, 45),
            v(5, "10 car features you never use", "US", 200, 6_000_000, 800_000, 720),
            v(6, "Cómo saber si tu batería está muriendo", "MX", 300, 2_000_000, 150_000, 480)]
    red = [dict(id="us:x", pais="EUA", texto="why does my car shake when i brake at high speed", pontos=8),
           dict(id="mx:y", pais="México", texto="por qué mi carro huele a gasolina adentro", pontos=6)]
    return duv, separar_prazos(vids), red


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--paises", help="ex.: US,MX,PT (padrão: rodízio da semana)")
    ap.add_argument("--oferta", type=int, default=10, help="quantas dúvidas checar no YouTube BR (100 unid. cada)")
    a = ap.parse_args()
    agora = dt.datetime.now(dt.timezone.utc)
    hoje = dt.datetime.now().date()
    sem = semana_iso(hoje)
    paises = a.paises.split(",") if a.paises else list(GRUPOS[sem % len(GRUPOS)])
    sementes_semana = {lang: [s[(sem * 3 + i) % len(s)] for i in range(3)] for lang, s in SEMENTES.items()}
    PASTA.mkdir(exist_ok=True)
    hist = carregar_hist()
    avisos = {}

    if a.demo:
        duvidas, prazos, red = demo(agora)
    else:
        RD.carregar_env()
        chave = os.environ.get("YOUTUBE_API_KEY")
        if not chave:
            raise SystemExit("Defina YOUTUBE_API_KEY.")
        cota = RD.Cota(); yt = RD.YouTube(chave, cota)
        print("1/4 dúvidas reais no Brasil (autocompletar)...")
        duvidas, falhas, total = duvidas_br()
        if falhas > total * .8:
            avisos["duvidas"] = "O autocompletar do Google não respondeu nesta rodada."
        duvidas = filtrar_novos(duvidas, lambda x: norm(x["texto"]), hist, "duvidas", hoje)
        print(f"   {len(duvidas)} dúvidas novas; medindo oferta em PT das {a.oferta} primeiras...")
        medir_oferta(yt, duvidas, agora, a.oferta)
        duvidas[:a.oferta] = sorted(duvidas[:a.oferta], key=lambda x: (not x.get("brecha"), -x["pontos"]))
        print(f"2/4 lá fora: {', '.join(paises)} · sementes {sementes_semana}")
        achados = la_fora(yt, paises, sementes_semana, agora)
        vids = montar_la_fora(yt, achados, agora)
        vids = filtrar_novos(vids, lambda v: v["id"], hist, "videos", hoje, dias=120)
        prazos = separar_prazos(vids)
        print("3/4 dúvidas lá fora (EUA e México)...")
        red, falhas_f, total_f = duvidas_fora()
        if falhas_f > total_f * .8:
            avisos["fora"] = "O autocompletar em inglês/espanhol não respondeu nesta rodada."
        red = filtrar_novos(red, lambda r: r["id"], hist, "fora", hoje)
        print(f"   cota usada ≈ {cota.usado}")
    print("4/4 calendário...")
    cal = calendario(hoje)

    d = dict(gerado_em=agora.isoformat(), gerado_legivel=dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
             paises=paises, sementes=sementes_semana, duvidas=duvidas[:40], la_fora=prazos,
             calendario=cal, avisos=avisos, duvidas_fora=red[:30])
    if not a.demo:
        registrar(d["duvidas"][:30], lambda x: norm(x["texto"]), hist, "duvidas", hoje)
        for lst in prazos.values():
            registrar(lst, lambda v: v["id"], hist, "videos", hoje)
        registrar(d["duvidas_fora"], lambda r: r["id"], hist, "fora", hoje)
        (PASTA / "historico.json").write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    sufixo = "_DEMO" if a.demo else ""
    (PASTA / f"ultimo{sufixo}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    nome = PASTA / f"ideias_{dt.datetime.now().strftime('%Y-%m-%d_%Hh%M')}{sufixo}.html"
    nome.write_text(html_relatorio(d), encoding="utf-8")
    print("pronto:", nome)


if __name__ == "__main__":
    main()
