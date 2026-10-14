#!/usr/bin/env python3
"""
Desempenho do canal: views dos vídeos publicados nos últimos dias (usa a mesma YOUTUBE_API_KEY).
Gera desempenho/ultimo.json, que a rotina de sexta usa para escolher o tema do vídeo longo da semana.

    python desempenho.py                 # canal definido na variável CANAL (ex.: @garagemtecnica ou UC...)
    python desempenho.py --dias 7
Cota: ~5 unidades por rodada.
"""
import argparse, datetime as dt, json, os
from pathlib import Path
import radar as RD

AQUI = Path(__file__).resolve().parent


def canal_uploads(yt, canal):
    if canal.startswith("UC"):
        r = yt.get("channels", part="contentDetails,snippet,statistics", id=canal)
    else:
        r = yt.get("channels", part="contentDetails,snippet,statistics", forHandle=canal.lstrip("@"))
    itens = r.get("items", [])
    if not itens:
        raise SystemExit(f"Canal '{canal}' não encontrado. Confira a variável CANAL (ex.: @seucanal).")
    c = itens[0]
    return c["id"], c["snippet"]["title"], c["contentDetails"]["relatedPlaylists"]["uploads"], c.get("statistics", {})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dias", type=int, default=7)
    a = p.parse_args()
    RD.carregar_env()
    chave, canal = os.environ.get("YOUTUBE_API_KEY"), os.environ.get("CANAL", "").strip()
    if not chave or not canal:
        raise SystemExit("Defina YOUTUBE_API_KEY e CANAL.")
    c = RD.Cota(); yt = RD.YouTube(chave, c)
    agora = dt.datetime.now(dt.timezone.utc)
    cid, nome, uploads, stats = canal_uploads(yt, canal)
    r = yt.get("playlistItems", part="contentDetails", playlistId=uploads, maxResults=50)
    ids = [i["contentDetails"]["videoId"] for i in r.get("items", [])]
    vids = []
    for v in (yt.videos(ids) if ids else []):
        sn, st = v["snippet"], v.get("statistics", {})
        pub = dt.datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
        dur = RD.duracao_s(v.get("contentDetails", {}).get("duration"))
        vids.append(dict(id=v["id"], titulo=sn["title"], publicado=sn["publishedAt"], dias=round((agora - pub).total_seconds() / 86400, 1),
                         formato="short" if dur <= 180 else "longo", duracao_s=dur,
                         views=int(st.get("viewCount", 0) or 0), likes=int(st.get("likeCount", 0) or 0),
                         comentarios=int(st.get("commentCount", 0) or 0), url=f"https://www.youtube.com/watch?v={v['id']}"))
    semana = sorted([v for v in vids if v["dias"] <= a.dias], key=lambda v: -v["views"])
    shorts = [v for v in semana if v["formato"] == "short"]
    out = dict(gerado_em=agora.isoformat(), canal=dict(id=cid, nome=nome, inscritos=int(stats.get("subscriberCount", 0) or 0),
                                                       views=int(stats.get("viewCount", 0) or 0)),
               janela_dias=a.dias, short_mais_visto=shorts[0] if shorts else None, semana=semana, todos=vids)
    pasta = AQUI / "desempenho"; pasta.mkdir(exist_ok=True)
    (pasta / "ultimo.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / f"{agora.astimezone().strftime('%Y-%m-%d')}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{nome}: {len(semana)} vídeos nos últimos {a.dias} dias · cota ≈ {c.usado}")
    for v in semana[:10]:
        print(f"  {v['views']:>8} views · {v['formato']:5} · {v['titulo']}")
    if shorts:
        print(f"\nShort mais visto: {shorts[0]['titulo']} ({shorts[0]['views']} views)")


if __name__ == "__main__":
    main()
