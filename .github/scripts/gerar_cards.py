#!/usr/bin/env python3
"""
Gera três cards em SVG (estatísticas, linguagens e sequência de contribuições)
usando a API do próprio GitHub. Roda dentro do GitHub Actions com o GITHUB_TOKEN
que o GitHub já fornece, então não depende de serviços de terceiros.

Variáveis de ambiente:
    GITHUB_TOKEN  token do Actions (obrigatório, a não ser que use DADOS_TESTE)
    LOGIN         usuário do GitHub (padrão: Cardoso-G-Ao)
    SAIDA         pasta de saída (padrão: dist)
    DADOS_TESTE   caminho de um JSON com a resposta da API, para testar sem rede
"""
import html
import json
import os
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

LOGIN = os.environ.get("LOGIN") or "Cardoso-G-Ao"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
SAIDA = Path(os.environ.get("SAIDA", "dist"))

# Tema "radical"
FUNDO, BORDA = "#141321", "#3a3a5c"
TITULO, TEXTO, DESTAQUE, ICONE = "#fe428e", "#a9fef7", "#fe428e", "#f8d847"
FONTE = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

CONSULTA = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def esc(texto) -> str:
    return html.escape(str(texto), quote=True)


def num(valor) -> str:
    """1234 -> 1.234 (padrão brasileiro)."""
    return f"{int(valor):,}".replace(",", ".")


def pct(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + "%"


def buscar_dados() -> dict:
    teste = os.environ.get("DADOS_TESTE")
    if teste:
        return json.loads(Path(teste).read_text(encoding="utf-8"))["data"]["user"]
    if not TOKEN:
        sys.exit("GITHUB_TOKEN não definido.")
    corpo = json.dumps({"query": CONSULTA, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=corpo,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "gerar-cards"})
    with urllib.request.urlopen(req, timeout=30) as resposta:
        dados = json.load(resposta)
    usuario = (dados.get("data") or {}).get("user")
    if "errors" in dados or not usuario:
        sys.exit(f"Erro na API do GitHub: {json.dumps(dados.get('errors', dados))[:500]}")
    return usuario


# ---------------------------------------------------------------------------
# Peças comuns dos SVGs
# ---------------------------------------------------------------------------
def moldura(largura: int, altura: int, titulo: str, corpo: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" aria-label="{esc(titulo)}">'
        f'<style>'
        f'.t{{font:600 18px {FONTE};fill:{TITULO}}}'
        f'.l{{font:400 14px {FONTE};fill:{TEXTO}}}'
        f'.v{{font:700 14px {FONTE};fill:{TEXTO}}}'
        f'.g{{font:700 30px {FONTE};fill:{TEXTO}}}'
        f'.p{{font:400 12px {FONTE};fill:{TEXTO};opacity:.75}}'
        f'</style>'
        f'<rect x="0.5" y="0.5" width="{largura - 1}" height="{altura - 1}" rx="10" fill="{FUNDO}" stroke="{BORDA}"/>'
        f'<text x="25" y="36" class="t">{esc(titulo)}</text>{corpo}</svg>'
    )


# ---------------------------------------------------------------------------
# Card 1: estatísticas
# ---------------------------------------------------------------------------
def card_estatisticas(u: dict) -> str:
    repos = u["repositories"]["nodes"]
    estrelas = sum(r["stargazerCount"] for r in repos)
    colecao = u["contributionsCollection"]
    itens = [
        ("Contribuições no último ano", colecao["contributionCalendar"]["totalContributions"]),
        ("Commits no último ano", colecao["totalCommitContributions"]),
        ("Pull requests", u["pullRequests"]["totalCount"]),
        ("Issues", u["issues"]["totalCount"]),
        ("Estrelas recebidas", estrelas),
        ("Repositórios públicos", u["repositories"]["totalCount"]),
    ]
    corpo = ""
    for i, (rotulo, valor) in enumerate(itens):
        y = 72 + i * 30
        corpo += (f'<circle cx="31" cy="{y - 5}" r="4.5" fill="{ICONE}"/>'
                  f'<text x="46" y="{y}" class="l">{esc(rotulo)}</text>'
                  f'<text x="440" y="{y}" class="v" text-anchor="end">{num(valor)}</text>')
    return moldura(470, 72 + len(itens) * 30 - 6, f"Estatísticas de {u.get('name') or LOGIN}", corpo)


# ---------------------------------------------------------------------------
# Card 2: linguagens mais usadas
# ---------------------------------------------------------------------------
def card_linguagens(u: dict) -> str:
    total_por_lang: dict[str, list] = {}
    for repo in u["repositories"]["nodes"]:
        for aresta in repo["languages"]["edges"]:
            nome = aresta["node"]["name"]
            cor = aresta["node"]["color"] or "#8b949e"
            atual = total_por_lang.setdefault(nome, [0, cor])
            atual[0] += aresta["size"]
    ranking = sorted(total_por_lang.items(), key=lambda x: x[1][0], reverse=True)[:6]
    soma = sum(v[0] for _, v in ranking) or 1

    largura, barra_x, barra_larg = 470, 25, 420
    segmentos, x = "", float(barra_x)
    for nome, (tamanho, cor) in ranking:
        w = barra_larg * tamanho / soma
        segmentos += f'<rect x="{x:.2f}" y="56" width="{w:.2f}" height="10" fill="{esc(cor)}"/>'
        x += w
    corpo = (f'<clipPath id="b"><rect x="{barra_x}" y="56" width="{barra_larg}" height="10" rx="5"/></clipPath>'
             f'<g clip-path="url(#b)">{segmentos}</g>')
    for i, (nome, (tamanho, cor)) in enumerate(ranking):
        col, linha = i % 2, i // 2
        x0, y = 25 + col * 215, 98 + linha * 26
        corpo += (f'<circle cx="{x0 + 5}" cy="{y - 5}" r="5" fill="{esc(cor)}"/>'
                  f'<text x="{x0 + 18}" y="{y}" class="l">{esc(nome)} <tspan class="p">{pct(100 * tamanho / soma)}</tspan></text>')
    altura = 98 + ((len(ranking) + 1) // 2) * 26 - 4
    return moldura(largura, max(altura, 120), "Linguagens mais usadas", corpo)


# ---------------------------------------------------------------------------
# Card 3: sequência de contribuições
# ---------------------------------------------------------------------------
def calcular_sequencias(dias: list[tuple[date, int]]):
    maior = atual_maior = 0
    ini_maior = fim_maior = ini_atual_tmp = None
    for d, c in dias:
        if c > 0:
            if atual_maior == 0:
                ini_atual_tmp = d
            atual_maior += 1
            if atual_maior > maior:
                maior, ini_maior, fim_maior = atual_maior, ini_atual_tmp, d
        else:
            atual_maior = 0
    # sequência atual: conta de trás para frente (se hoje ainda está zerado, começa de ontem)
    i = len(dias) - 1
    if i >= 0 and dias[i][1] == 0:
        i -= 1
    atual, ini_atual, fim_atual = 0, None, None
    while i >= 0 and dias[i][1] > 0:
        if atual == 0:
            fim_atual = dias[i][0]
        atual += 1
        ini_atual = dias[i][0]
        i -= 1
    return atual, ini_atual, fim_atual, maior, ini_maior, fim_maior


def curto(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "-"


def card_sequencia(u: dict) -> str:
    cal = u["contributionsCollection"]["contributionCalendar"]
    dias = sorted((datetime.strptime(d["date"], "%Y-%m-%d").date(), d["contributionCount"])
                  for w in cal["weeks"] for d in w["contributionDays"])
    atual, a_ini, a_fim, maior, m_ini, m_fim = calcular_sequencias(dias)
    periodo = f'{curto(dias[0][0])} - {curto(dias[-1][0])}' if dias else ""

    def periodo_seq(ini, fim, n):
        return f"{curto(ini)} - {curto(fim)}" if n else "Sem sequência ativa"

    corpo = (
        # coluna 1: total
        f'<text x="85" y="95" class="g" text-anchor="middle">{num(cal["totalContributions"])}</text>'
        f'<text x="85" y="122" class="l" text-anchor="middle">Contribuições</text>'
        f'<text x="85" y="142" class="p" text-anchor="middle">{esc(periodo)}</text>'
        # divisor
        f'<line x1="165" y1="62" x2="165" y2="150" stroke="{BORDA}"/>'
        # coluna 2: sequência atual (com anel)
        f'<circle cx="235" cy="92" r="34" fill="none" stroke="{DESTAQUE}" stroke-width="4"/>'
        f'<text x="235" y="102" class="g" text-anchor="middle">{atual}</text>'
        f'<text x="235" y="148" class="l" text-anchor="middle" fill="{ICONE}">Sequência atual</text>'
        f'<text x="235" y="166" class="p" text-anchor="middle">{esc(periodo_seq(a_ini, a_fim, atual))}</text>'
        # divisor
        f'<line x1="305" y1="62" x2="305" y2="150" stroke="{BORDA}"/>'
        # coluna 3: maior sequência
        f'<text x="385" y="95" class="g" text-anchor="middle">{maior}</text>'
        f'<text x="385" y="122" class="l" text-anchor="middle">Maior sequência</text>'
        f'<text x="385" y="142" class="p" text-anchor="middle">{esc(periodo_seq(m_ini, m_fim, maior))}</text>'
    )
    return moldura(470, 182, "Sequência de contribuições", corpo)


def main():
    usuario = buscar_dados()
    SAIDA.mkdir(parents=True, exist_ok=True)
    for arquivo, gerar in (("stats.svg", card_estatisticas),
                           ("langs.svg", card_linguagens),
                           ("streak.svg", card_sequencia)):
        (SAIDA / arquivo).write_text(gerar(usuario), encoding="utf-8")
        print("gerado:", SAIDA / arquivo)


if __name__ == "__main__":
    main()
