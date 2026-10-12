#!/usr/bin/env python3
"""
Radar de tendências: o que cresce no YouTube dos EUA e ainda tem pouca oferta no Brasil.

Uso:
    python radar.py --nicho carros               # coleta real (precisa da chave)
    python radar.py --nicho carros --top 25 --dias 21
    python radar.py --demo                       # dados fictícios, só para testar

Chaves (variáveis de ambiente ou arquivo radar.env ao lado do script):
    YOUTUBE_API_KEY=...        obrigatória (Google Cloud > YouTube Data API v3)
    ANTHROPIC_API_KEY=...      opcional: agrupa títulos em temas e traduz para PT-BR com IA

Só usa a biblioteca padrão do Python 3.9+.
"""
import argparse, csv, datetime as dt, html, json, math, os, re, sys, time
import urllib.parse, urllib.request, urllib.error
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
YT = "https://www.googleapis.com/youtube/v3/"

# ------------------------------------------------------------------ nichos
NICHOS = {
    "carros": dict(
        categoria="2",  # Autos & Vehicles
        sementes=["car review", "hybrid car", "electric car", "car maintenance", "car buying tips",
                  "car problems", "best cars", "new car", "car mechanic", "car technology"],
        glossario={
            "car": "carro", "cars": "carros", "hybrid": "híbrido", "electric": "elétrico", "ev": "carro elétrico",
            "review": "review", "maintenance": "manutenção", "engine": "motor", "battery": "bateria",
            "transmission": "câmbio", "brakes": "freios", "tires": "pneus", "oil": "óleo", "change": "troca",
            "problems": "problemas", "buying": "comprar", "buy": "comprar", "tips": "dicas", "best": "melhores",
            "worst": "piores", "reliable": "confiáveis", "cheap": "baratos", "used": "usado", "new": "novo",
            "plug-in": "plug-in", "charging": "recarga", "range": "autonomia", "mileage": "quilometragem",
            "fuel": "combustível", "economy": "economia", "turbo": "turbo", "suv": "suv", "pickup": "picape",
            "truck": "picape", "mechanic": "mecânico", "dealership": "concessionária", "warranty": "garantia",
            "insurance": "seguro", "repair": "conserto", "cvt": "cvt", "diesel": "diesel", "test": "teste",
            "crash": "batida", "safety": "segurança", "autopilot": "piloto automático", "self-driving": "direção autônoma",
            "myths": "mitos", "pressure": "pressão", "reliability": "confiabilidade", "cost": "custo",
            "replacement": "troca", "winter": "inverno", "owners": "donos", "mistakes": "erros", "scam": "golpe",
            "pads": "pastilhas", "long": "longo", "term": "prazo", "tested": "testado", "miles": "milhas",
        },
        frases={
            "oil change": "troca de óleo", "car maintenance": "manutenção do carro", "tire pressure": "calibragem dos pneus",
            "cvt transmission": "câmbio cvt", "battery replacement": "troca de bateria", "used car": "carro usado",
            "used car buying": "comprar carro usado", "car buying": "comprar carro", "electric car range": "autonomia carro elétrico",
            "plug-in hybrid": "híbrido plug-in", "brake pads": "pastilha de freio", "turbo engine": "motor turbo",
            "long term review": "avaliação de longo prazo", "fuel economy": "consumo de combustível",
            "self-driving cars": "carros autônomos", "hybrid car battery": "bateria carro híbrido",
            "hybrid car": "carro híbrido", "electric car": "carro elétrico", "oil change myths": "mitos troca de óleo",
            "tire pressure myths": "mitos calibragem pneus", "turbo engine problems": "problemas motor turbo",
            "cvt transmission problems": "problemas câmbio cvt", "car maintenance tips": "dicas manutenção carro",
            "used car buying tips": "dicas comprar carro usado", "used car buying mistakes": "erros comprar carro usado",
        },
    ),
    "reforma": dict(
        categoria="26",  # Howto & Style
        sementes=["home renovation", "diy home improvement", "bathroom remodel", "kitchen remodel",
                  "flooring installation", "home repair tips", "renovation mistakes", "small apartment makeover"],
        glossario={
            "home": "casa", "renovation": "reforma", "remodel": "reforma", "bathroom": "banheiro",
            "kitchen": "cozinha", "flooring": "piso", "floor": "piso", "tile": "revestimento", "paint": "pintura",
            "painting": "pintura", "wall": "parede", "walls": "paredes", "mistakes": "erros", "tips": "dicas",
            "diy": "faça você mesmo", "cheap": "barato", "budget": "barato", "small": "pequeno",
            "apartment": "apartamento", "makeover": "transformação", "shower": "box", "waterproofing": "impermeabilização",
            "drywall": "drywall", "lighting": "iluminação", "repair": "conserto", "roof": "telhado",
        },
        frases={"bathroom remodel": "reforma de banheiro", "kitchen remodel": "reforma de cozinha",
                "home renovation": "reforma de casa", "renovation mistakes": "erros de reforma",
                "flooring installation": "instalação de piso", "small apartment": "apartamento pequeno"},
    ),
    "investimentos": dict(
        categoria="27",  # Education (finanças não tem categoria própria)
        sementes=["investing for beginners", "personal finance", "passive income", "dividend investing",
                  "index funds", "how to save money", "retirement planning", "inflation explained"],
        glossario={
            "investing": "investir", "investment": "investimento", "beginners": "iniciantes", "personal": "pessoais",
            "finance": "finanças", "passive": "passiva", "income": "renda", "dividend": "dividendos",
            "dividends": "dividendos", "index": "índice", "funds": "fundos", "save": "economizar", "money": "dinheiro",
            "retirement": "aposentadoria", "inflation": "inflação", "explained": "explicada", "debt": "dívidas",
            "budget": "orçamento", "compound": "juros", "interest": "compostos", "taxes": "impostos",
        },
        frases={"passive income": "renda passiva", "index funds": "fundos de índice", "personal finance": "finanças pessoais",
                "compound interest": "juros compostos", "dividend investing": "investir em dividendos",
                "retirement planning": "planejamento aposentadoria", "emergency fund": "reserva de emergência"},
    ),
}

MARCAS = set("""tesla byd toyota honda ford chevrolet chevy gm hyundai kia nissan volkswagen vw fiat jeep renault
peugeot citroen bmw mercedes audi volvo porsche ferrari lamborghini mazda subaru mitsubishi lexus rivian lucid
gwm haval caoa chery jac omoda geely xiaomi polestar mini ram dodge model corolla civic hilux compass""".split())

STOP = set("""a an the and or of to in on for with without from by at is are was were be been this that these those
it its my your our their his her i you we they me us them what why how when which who vs versus not no yes do does did
just only more most very really new 2024 2025 2026 2027 2028 best worst top ever all one two three first last here
there about after before into over under than then so too can could should would will get got make made watch video
full part ft feat official shorts short live episode ep day days year years""".split())

# ------------------------------------------------------------------ util
def carregar_env():
    f = AQUI / "radar.env"
    if f.exists():
        for linha in f.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.strip().startswith("#"):
                k, v = linha.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def duracao_s(iso):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def idade_dias(publicado, agora):
    t = dt.datetime.fromisoformat(publicado.replace("Z", "+00:00"))
    return max(1.0, (agora - t).total_seconds() / 86400)


class Cota:
    def __init__(self):
        self.usado = 0
    CUSTO = {"search": 100, "videos": 1, "channels": 1}


class YouTube:
    def __init__(self, chave, cota):
        self.chave, self.cota = chave, cota

    def get(self, recurso, **params):
        params["key"] = self.chave
        url = YT + recurso + "?" + urllib.parse.urlencode(params)
        for tentativa in range(3):
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    self.cota.usado += Cota.CUSTO.get(recurso, 1)
                    return json.load(r)
            except urllib.error.HTTPError as e:
                corpo = e.read().decode("utf-8", "replace")
                if "quotaExceeded" in corpo or "dailyLimitExceeded" in corpo:
                    raise SystemExit("Cota diária da YouTube API esgotada. Rode de novo amanhã ou reduza --top/--sementes.")
                if e.code in (500, 503) and tentativa < 2:
                    time.sleep(2 * (tentativa + 1)); continue
                raise SystemExit(f"Erro da YouTube API ({e.code}): {corpo[:400]}")
            except urllib.error.URLError as e:
                if tentativa < 2:
                    time.sleep(2); continue
                raise SystemExit(f"Sem conexão com a YouTube API: {e}")

    def buscar(self, q, regiao, idioma, depois, n=25):
        r = self.get("search", part="id", q=q, type="video", order="viewCount", maxResults=n,
                     regionCode=regiao, relevanceLanguage=idioma, publishedAfter=depois)
        return [i["id"]["videoId"] for i in r.get("items", []) if i.get("id", {}).get("videoId")]

    def populares(self, regiao, categoria, n=50):
        try:
            r = self.get("videos", part="id", chart="mostPopular", regionCode=regiao,
                         videoCategoryId=categoria, maxResults=n)
            return [i["id"] for i in r.get("items", [])]
        except SystemExit:
            return []  # algumas categorias não têm ranking em algumas regiões

    def videos(self, ids):
        out = []
        for i in range(0, len(ids), 50):
            r = self.get("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]))
            out += r.get("items", [])
        return out

    def canais(self, ids):
        out = {}
        for i in range(0, len(ids), 50):
            r = self.get("channels", part="statistics,snippet", id=",".join(ids[i:i + 50]))
            for c in r.get("items", []):
                st = c.get("statistics", {})
                out[c["id"]] = dict(nome=c["snippet"]["title"],
                                    inscritos=int(st.get("subscriberCount", 0) or 0))
        return out


def autocomplete_br(q):
    """Sugestões de busca do YouTube em PT-BR (endpoint público, sem cota). Retorna lista de sugestões."""
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        dict(client="firefox", ds="yt", hl="pt-BR", gl="br", q=q))
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            dados = json.loads(r.read().decode("utf-8", "replace"))
            return dados[1] if len(dados) > 1 else []
    except Exception:
        return None  # indisponível: não pesa no score


# ------------------------------------------------------------------ métricas
def enriquecer(itens, canais, agora):
    vids = []
    for v in itens:
        st, sn = v.get("statistics", {}), v["snippet"]
        views = int(st.get("viewCount", 0) or 0)
        idade = idade_dias(sn["publishedAt"], agora)
        insc = canais.get(sn["channelId"], {}).get("inscritos", 0)
        dur = duracao_s(v.get("contentDetails", {}).get("duration"))
        vids.append(dict(
            id=v["id"], titulo=sn["title"], canal=sn.get("channelTitle", ""), views=views, idade=idade,
            vpd=views / idade, inscritos=insc, outlier=views / max(insc, 1000), duracao=dur, short=dur <= 180,
            url=f"https://www.youtube.com/watch?v={v['id']}"))
    return vids


# ------------------------------------------------------------------ temas
GENERICOS = {"long term", "replacement cost", "what happened", "nobody talks", "here's what", "you need",
             "need to know", "things you", "should you", "worth it", "the truth"}


def temas_heuristica(vids, glossario, max_temas, frases=None):
    """Agrupa por expressões (2-3 palavras) que se repetem nos títulos; nomes de modelos ficam como estão."""
    pontos, membros, forma = defaultdict(float), defaultdict(set), {}
    for v in vids:
        palavras = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\+']*", v["titulo"])
        toks = [(p.lower(), p) for p in palavras]
        vistos = set()
        for n in (2, 3):
            for i in range(len(toks) - n + 1):
                g = toks[i:i + n]
                if g[0][0] in STOP or g[-1][0] in STOP or all(t[0] in STOP for t in g):
                    continue
                if g[0][0][0].isdigit():
                    continue
                chave = " ".join(t[0] for t in g)
                if chave in GENERICOS or chave in vistos:
                    continue
                vistos.add(chave)
                pontos[chave] += math.log10(1 + v["vpd"]) * (1 + min(v["outlier"], 5) / 5)
                membros[chave].add(v["id"])
                forma.setdefault(chave, " ".join(t[1] for t in g))
    # precisa aparecer em pelo menos 2 vídeos de canais diferentes
    por_id = {v["id"]: v for v in vids}
    cand = []
    for k, s in pontos.items():
        ids = membros[k]
        if len(ids) < 2 or len({por_id[i]["canal"] for i in ids}) < 2:
            continue
        cand.append((s, k))
    cand.sort(reverse=True)
    temas, usados = [], []
    for s, k in cand:
        # evita temas quase iguais: texto contido no outro ou mesmos vídeos
        if any(k in u or u in k for u in usados):
            continue
        if any(len(membros[k] & membros[u]) / len(membros[k] | membros[u]) > 0.5 for u in usados):
            continue
        usados.append(k)
        pt, ok = traduzir(forma[k], glossario, frases)
        temas.append(dict(tema_en=forma[k], tema_pt=pt, busca_pt=pt, traducao_ok=ok, ids=sorted(membros[k])))
        if len(temas) >= max_temas:
            break
    return temas


def traduzir(expr, glossario, frases=None):
    """Tradução simples para o termo de busca. Devolve (texto, confiável?)."""
    frases = frases or {}
    l = expr.lower()
    if l in frases:
        return frases[l], True
    palavras = expr.split()
    marca = any(p.lower() in MARCAS for p in palavras)
    out, ok = [], True
    for p in palavras:
        pl = p.lower()
        if pl in glossario:
            out.append(glossario[pl])
        elif pl in MARCAS or any(c.isdigit() for c in p) or pl == "vs":
            out.append(p)
        else:
            out.append(p); ok = False
    if not marca:
        out = out[::-1]  # inglês: modificador antes ("used car buying" -> "comprar carro usado")
    return " ".join(out), ok


def temas_ia(vids, nicho, max_temas, chave):
    """Agrupa títulos em temas e propõe a busca em PT-BR usando o Claude."""
    top = sorted(vids, key=lambda v: v["vpd"], reverse=True)[:150]
    linhas = "\n".join(f'{v["id"]}\t{int(v["vpd"])}\t{v["titulo"]}' for v in top)
    prompt = f"""Você é pesquisador de pauta de um canal brasileiro de YouTube sobre {nicho}.
Abaixo estão vídeos em alta nos EUA (id, views por dia, título). Agrupe em até {max_temas} TEMAS de pauta
(assunto, não vídeo específico), ignorando publi, vlogs pessoais e assuntos que não fazem sentido no Brasil
(ex.: produto ou lei que só existe nos EUA, sem equivalente aqui).
Para cada tema, devolva o termo que um brasileiro digitaria no YouTube para procurar esse assunto.
Responda SOMENTE com JSON: [{{"tema_en": "...", "tema_pt": "...", "busca_pt": "...", "angulo_br": "uma frase com o ângulo para o público brasileiro", "ids": ["id", ...]}}]

{linhas}"""
    corpo = json.dumps(dict(model=os.environ.get("RADAR_MODELO", "claude-haiku-5-5"), max_tokens=4000,
                            messages=[dict(role="user", content=prompt)])).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=corpo, headers={
        "x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        texto = json.load(r)["content"][0]["text"]
    texto = texto[texto.find("["): texto.rfind("]") + 1]
    validos = {v["id"] for v in vids}
    temas = []
    for t in json.loads(texto):
        ids = [i for i in t.get("ids", []) if i in validos]
        if ids and t.get("busca_pt"):
            temas.append(dict(tema_en=t["tema_en"], tema_pt=t.get("tema_pt", t["busca_pt"]),
                              busca_pt=t["busca_pt"], angulo_br=t.get("angulo_br", ""), traducao_ok=True, ids=ids))
    return temas[:max_temas]


# ------------------------------------------------------------------ score
def pontuar(temas, vids_eua, br):
    por_id = {v["id"]: v for v in vids_eua}
    for t in temas:
        vs = [por_id[i] for i in t["ids"]]
        t["n_eua"] = len(vs)
        t["vpd_eua"] = sum(v["vpd"] for v in vs)
        t["outlier_max"] = max(v["outlier"] for v in vs)
        t["exemplos_eua"] = sorted(vs, key=lambda v: v["vpd"], reverse=True)[:3]
        b = br.get(t["busca_pt"], {})
        t.update({k: b.get(k) for k in ("n_br", "top5_br", "recentes_br", "melhor_br", "sugestoes_br")})
    # demanda EUA normalizada 0-100 (log)
    mx = max((math.log10(1 + t["vpd_eua"]) for t in temas), default=1) or 1
    for t in temas:
        demanda = 100 * math.log10(1 + t["vpd_eua"]) / mx
        demanda *= 1 + min(t["outlier_max"], 10) / 20  # tema puxado por canal pequeno = demanda real
        top5 = t["top5_br"] or 0
        saturacao = min(1.0, math.log10(1 + top5) / 7)  # ~10 milhões de views no top 5 = saturado
        sug = t["sugestoes_br"]
        fator_busca = 1.0 if sug is None else 0.6 + 0.04 * min(len(sug), 10)
        t["demanda"] = round(min(demanda, 150), 1)
        t["saturacao"] = round(saturacao, 2)
        t["oportunidade"] = round(demanda * fator_busca * (1 - 0.85 * saturacao), 1)
    temas.sort(key=lambda t: t["oportunidade"], reverse=True)
    return temas


def medir_br(yt, temas, agora, n_temas):
    br = {}
    depois = (agora - dt.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for t in temas[:n_temas]:
        q = t["busca_pt"]
        if q in br:
            continue
        ids = yt.buscar(q, "BR", "pt", depois, n=25)
        itens = yt.videos(ids) if ids else []
        vs = enriquecer(itens, {}, agora)
        vs.sort(key=lambda v: v["views"], reverse=True)
        br[q] = dict(
            n_br=len(vs), top5_br=sum(v["views"] for v in vs[:5]),
            recentes_br=sum(1 for v in vs if v["idade"] <= 90),
            melhor_br=vs[0] if vs else None, sugestoes_br=autocomplete_br(q))
        print(f"  BR: {q!r}: {len(vs)} vídeos, top 5 = {br[q]['top5_br']:,} views", flush=True)
    return br


# ------------------------------------------------------------------ relatório
def fmt(n):
    if n is None:
        return "–"
    n = float(n)
    for lim, suf in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if n >= lim:
            return f"{n / lim:.1f}{suf}".replace(".", ",")
    return f"{int(n)}"


def salvar_csv(temas, caminho):
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["posição", "oportunidade", "tema (EUA)", "busca no Brasil", "ângulo BR", "vídeos EUA",
                    "views/dia EUA", "outlier máx", "vídeos BR (12 meses)", "views top 5 BR",
                    "BR últimos 90 dias", "sugestões de busca BR", "saturação BR", "tradução confiável"])
        for i, t in enumerate(temas, 1):
            sug = t["sugestoes_br"]
            w.writerow([i, t["oportunidade"], t["tema_en"], t["busca_pt"], t.get("angulo_br", ""), t["n_eua"],
                        int(t["vpd_eua"]), round(t["outlier_max"], 1), t["n_br"], t["top5_br"], t["recentes_br"],
                        "" if sug is None else len(sug), t["saturacao"], "sim" if t["traducao_ok"] else "revisar"])


def salvar_html(temas, caminho, info):
    esc = html.escape
    linhas = []
    mx = max((t["oportunidade"] for t in temas), default=1) or 1
    for i, t in enumerate(temas, 1):
        ex = "".join(f'<li><a href="{esc(v["url"])}">{esc(v["titulo"])}</a> <span>{esc(v["canal"])} · '
                     f'{fmt(v["vpd"])}/dia · {v["outlier"]:.1f}× inscritos</span></li>' for v in t["exemplos_eua"])
        mb = t["melhor_br"]
        br_txt = (f'<a href="{esc(mb["url"])}">{esc(mb["titulo"])}</a> <span>{fmt(mb["views"])} views</span>'
                  if mb else "<span>nenhum vídeo relevante encontrado</span>")
        sug = t["sugestoes_br"]
        sug_txt = "não medido" if sug is None else (", ".join(esc(s) for s in sug[:5]) or "nenhuma")
        sat = t["saturacao"]
        selo = ("saturado", "sat") if sat > 0.8 else (("concorrido", "med") if sat > 0.55 else ("espaço livre", "ok"))
        rev = "" if t["traducao_ok"] else '<em class="rev">conferir tradução</em>'
        ang = f'<p class="ang">{esc(t["angulo_br"])}</p>' if t.get("angulo_br") else ""
        linhas.append(f"""
<article>
  <header><b>{i}</b><div><h2>{esc(t["busca_pt"])}</h2><small>EUA: {esc(t["tema_en"])} {rev}</small></div>
  <span class="tag {selo[1]}">{selo[0]}</span></header>
  <div class="bar"><i style="width:{100 * t['oportunidade'] / mx:.0f}%"></i></div>
  {ang}
  <dl>
    <div><dt>Oportunidade</dt><dd>{t["oportunidade"]:.0f}</dd></div>
    <div><dt>Views/dia EUA</dt><dd>{fmt(t["vpd_eua"])}</dd></div>
    <div><dt>Vídeos EUA</dt><dd>{t["n_eua"]}</dd></div>
    <div><dt>Top 5 BR (12m)</dt><dd>{fmt(t["top5_br"])}</dd></div>
    <div><dt>BR recentes</dt><dd>{t["recentes_br"] if t["recentes_br"] is not None else "–"}</dd></div>
  </dl>
  <h3>Em alta nos EUA (para estudar o assunto)</h3><ul>{ex}</ul>
  <h3>Maior vídeo no Brasil</h3><p class="br">{br_txt}</p>
  <h3>O brasileiro também busca</h3><p class="br">{sug_txt}</p>
</article>""")
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Radar de tendências</title>
<style>
:root{{--bg:#0a0f1e;--card:#131b32;--t:#ecf0f8;--m:#8794b2;--c:#3ac4ff;--a:#ffa826;--g:#48de84;--r:#ff6b6b;--l:#26304d}}
@media (prefers-color-scheme:light){{:root{{--bg:#f4f6fb;--card:#fff;--t:#111827;--m:#5b6478;--l:#dde2ee}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--t);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:900px;margin:auto;padding:24px 16px 60px}}h1{{font-size:28px;margin:0 0 4px}}
.info{{color:var(--m);margin:0 0 20px}}.aviso{{background:#ff6b6b22;border:1px solid var(--r);padding:10px 14px;border-radius:10px;margin-bottom:16px}}
article{{background:var(--card);border:1px solid var(--l);border-radius:16px;padding:18px;margin:14px 0}}
header{{display:flex;gap:14px;align-items:center}}header b{{font-size:26px;color:var(--c);min-width:34px}}
header div{{flex:1;min-width:0}}h2{{margin:0;font-size:20px}}small{{color:var(--m)}}
.tag{{font-size:12px;font-weight:600;padding:4px 10px;border-radius:99px;white-space:nowrap}}
.ok{{background:#48de8422;color:var(--g)}}.med{{background:#ffa82622;color:var(--a)}}.sat{{background:#ff6b6b22;color:var(--r)}}
.rev{{color:var(--a);font-style:normal;font-size:12px;margin-left:6px}}
.bar{{height:6px;background:var(--l);border-radius:3px;margin:12px 0}}.bar i{{display:block;height:100%;background:var(--c);border-radius:3px}}
.ang{{margin:6px 0 10px}}dl{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:0 0 6px}}
dl div{{background:var(--bg);border-radius:10px;padding:8px 10px}}dt{{color:var(--m);font-size:12px}}dd{{margin:0;font-weight:700;font-size:18px}}
h3{{font-size:13px;color:var(--m);margin:14px 0 4px;text-transform:uppercase;letter-spacing:.04em}}
ul{{margin:0;padding-left:18px}}li{{margin:3px 0}}a{{color:var(--c);text-decoration:none}}li span,.br span{{color:var(--m);font-size:13px}}
.br{{margin:0}}
</style></head><body><main>
<h1>Radar de tendências · {esc(info["nicho"])}</h1>
<p class="info">{esc(info["quando"])} · EUA últimos {info["dias"]} dias · {info["n_videos"]} vídeos analisados · cota usada ≈ {info["cota"]} unidades</p>
{'<p class="aviso">DADOS FICTÍCIOS (modo demo) — rode sem --demo com a sua chave para dados reais.</p>' if info["demo"] else ""}
<p class="info"><b>Oportunidade</b> = demanda nos EUA (views/dia, com bônus quando canais pequenos explodem) × busca no Brasil ÷ saturação no Brasil. Os vídeos gringos servem para estudar o assunto; o vídeo publicado deve ter roteiro próprio.</p>
{"".join(linhas)}
</main></body></html>"""
    Path(caminho).write_text(pagina, encoding="utf-8")


# ------------------------------------------------------------------ execução
def rodar(args):
    carregar_env()
    agora = dt.datetime.now(dt.timezone.utc)
    nicho = NICHOS[args.nicho]
    if args.demo:
        import radar_demo
        vids = radar_demo.videos(agora)
        temas = temas_heuristica(vids, nicho["glossario"], args.top * 3, nicho.get("frases"))
        temas = [t for t in temas if t["traducao_ok"]][:args.top]
        br = radar_demo.medir_br(temas)
        cota = 0
    else:
        chave = os.environ.get("YOUTUBE_API_KEY")
        if not chave:
            raise SystemExit("Defina YOUTUBE_API_KEY (variável de ambiente ou arquivo radar.env).")
        c = Cota(); yt = YouTube(chave, c)
        depois = (agora - dt.timedelta(days=args.dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ids = set(yt.populares("US", nicho["categoria"]))
        sementes = nicho["sementes"][:args.sementes]
        for s in sementes:
            print(f"EUA: buscando {s!r}", flush=True)
            ids.update(yt.buscar(s, "US", "en", depois, n=50))
        itens = yt.videos(sorted(ids))
        canais = yt.canais(sorted({i["snippet"]["channelId"] for i in itens}))
        vids = enriquecer(itens, canais, agora)
        vids = [v for v in vids if v["idade"] <= args.dias * 1.5 or v["vpd"] > 5000]
        if not args.shorts:
            vids = [v for v in vids if not v["short"]]
        print(f"{len(vids)} vídeos nos EUA. Agrupando temas...", flush=True)
        chave_ia = os.environ.get("ANTHROPIC_API_KEY")
        temas = None
        if chave_ia and not args.sem_ia:
            try:
                temas = temas_ia(vids, args.nicho, args.top, chave_ia)
                print(f"IA agrupou {len(temas)} temas.")
            except Exception as e:
                print(f"IA indisponível ({e}); usando agrupamento automático.")
        if not temas:
            temas = temas_heuristica(vids, nicho["glossario"], args.top * 3, nicho.get("frases"))
            revisar = [t for t in temas if not t["traducao_ok"]]
            temas = [t for t in temas if t["traducao_ok"]][:args.top]
            if revisar:
                print("Temas sem tradução confiável (fora da medição no Brasil; use a IA ou adicione ao glossário):")
                for t in revisar[:15]:
                    print("   -", t["tema_en"])
        br = medir_br(yt, temas, agora, args.top)
        cota = c.usado
    temas = pontuar(temas, vids, br)
    saida = AQUI / "relatorios"; saida.mkdir(exist_ok=True)
    base = saida / f"radar_{args.nicho}_{agora.astimezone().strftime('%Y-%m-%d_%Hh%M')}"
    salvar_csv(temas, base.with_suffix(".csv"))
    salvar_html(temas, base.with_suffix(".html"), dict(
        nicho=args.nicho, quando=agora.astimezone().strftime("%d/%m/%Y %H:%M"), dias=args.dias,
        n_videos=len(vids), cota=cota, demo=args.demo))
    print(f"\nTop {min(10, len(temas))}:")
    for i, t in enumerate(temas[:10], 1):
        print(f"{i:>2}. {t['oportunidade']:>5.0f}  {t['busca_pt']}  (EUA: {t['tema_en']}; saturação BR {t['saturacao']:.0%})")
    print(f"\nRelatório: {base.with_suffix('.html')}\nPlanilha:  {base.with_suffix('.csv')}")
    if not args.demo:
        print(f"Cota usada ≈ {cota} de 10.000 por dia.")


def main():
    p = argparse.ArgumentParser(description="Radar de tendências EUA → Brasil para YouTube")
    p.add_argument("--nicho", choices=NICHOS, default="carros")
    p.add_argument("--dias", type=int, default=30, help="janela de vídeos recentes nos EUA")
    p.add_argument("--top", type=int, default=20, help="quantos temas medir no Brasil (100 de cota cada)")
    p.add_argument("--sementes", type=int, default=10, help="quantas buscas nos EUA (100 de cota cada)")
    p.add_argument("--shorts", action="store_true", help="incluir Shorts na análise dos EUA")
    p.add_argument("--sem-ia", action="store_true", help="não usar o Claude para agrupar temas")
    p.add_argument("--demo", action="store_true", help="roda com dados fictícios, sem chave")
    rodar(p.parse_args())


if __name__ == "__main__":
    main()
