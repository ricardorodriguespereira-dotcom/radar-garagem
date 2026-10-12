"""Dados FICTÍCIOS para testar o radar sem chave de API. Nada aqui é real."""
import random, datetime as dt

TITULOS = [
    "Why Hybrid Cars Are Taking Over Again", "Hybrid Car Battery Replacement Cost Explained",
    "I Bought The Cheapest Hybrid Car And Here's What Happened", "Plug-In Hybrid vs Hybrid: Which Should You Buy?",
    "Plug-In Hybrid Mistakes Owners Make", "CVT Transmission Problems Nobody Talks About",
    "Why CVT Transmission Fails (And How To Avoid It)", "Car Maintenance Tips That Save Thousands",
    "10 Car Maintenance Tips Dealers Won't Tell You", "Turbo Engine Problems After 100k Miles",
    "Are Turbo Engine Cars Reliable Long Term?", "Electric Car Range In Winter Tested",
    "Real Electric Car Range vs EPA Numbers", "Used Car Buying Tips For 2026", "Used Car Buying Mistakes To Avoid",
    "BYD Dolphin Long Term Review", "BYD Dolphin vs Tesla Model 3", "Tire Pressure Myths Debunked",
    "Brake Pads Last Longer On Hybrids? Mechanic Explains", "Oil Change Intervals Are A Scam?",
    "Oil Change Myths Mechanics Hate", "Self-Driving Cars Tested In Rain",
]
CANAIS = ["MotorLab", "GarageTalk", "DriveSmart", "WrenchDaily", "AutoNerd", "TorqueTV", "CarClinic", "RoadTested"]


def videos(agora):
    rnd = random.Random(42)
    out = []
    for i, t in enumerate(TITULOS):
        for k in range(rnd.randint(1, 3)):
            idade = rnd.uniform(2, 30)
            vpd = rnd.lognormvariate(9, 1.1)
            insc = int(rnd.lognormvariate(12, 1.5))
            views = int(vpd * idade)
            out.append(dict(id=f"demo{i:02d}{k}", titulo=t if k == 0 else t.replace("Why", "How").replace("Explained", "Breakdown"),
                            canal=CANAIS[(i + k * 3) % len(CANAIS)], views=views, idade=idade, vpd=vpd,
                            inscritos=insc, outlier=views / max(insc, 1000), duracao=900, short=False,
                            url="https://www.youtube.com/results?search_query=" + t.replace(" ", "+")))
    return out


def medir_br(temas):
    rnd = random.Random(7)
    br = {}
    for t in temas:
        q = t["busca_pt"]
        n = rnd.randint(3, 25)
        top5 = int(rnd.lognormvariate(12.5, 2.2))
        br[q] = dict(n_br=n, top5_br=top5, recentes_br=rnd.randint(0, n), sugestoes_br=[f"{q} {s}" for s in
                     ("vale a pena", "problemas", "preço", "2026", "manutenção")[:rnd.randint(0, 5)]],
                     melhor_br=dict(titulo=f"[fictício] {q}", views=top5 // 3,
                                    url="https://www.youtube.com/results?search_query=" + q.replace(" ", "+")))
    return br
