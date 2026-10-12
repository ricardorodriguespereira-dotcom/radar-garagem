# Radar de tendências EUA → Brasil

Descobre temas que estão crescendo no YouTube dos EUA e mede quanto já existe sobre eles em português.
Resultado: um relatório HTML (abre no celular) e uma planilha CSV com os temas ranqueados por **oportunidade**.

Só precisa de Python 3.9+ (nenhuma biblioteca extra).

## 1. Criar a chave da YouTube Data API (gratuita, uma vez só)
1. Acesse https://console.cloud.google.com/ e crie um projeto (ex.: "radar-youtube").
2. Em **APIs e serviços > Biblioteca**, procure **YouTube Data API v3** e clique em **Ativar**.
3. Em **APIs e serviços > Credenciais > Criar credenciais > Chave de API**. Copie a chave.
4. (Recomendado) Em "Restringir chave", limite à YouTube Data API v3.

## 2. Configurar
Copie `radar.env.exemplo` para `radar.env` e cole a chave:
```
YOUTUBE_API_KEY=sua_chave_aqui
```
Opcional: `ANTHROPIC_API_KEY=...` faz o Claude agrupar os títulos em temas, traduzir para o termo que o brasileiro
busca e sugerir o ângulo para o público BR. Sem ela, o radar usa um agrupamento automático mais simples.

## 3. Rodar
```
python radar.py --demo                 # teste com dados fictícios
python radar.py --nicho carros         # coleta real
python radar.py --nicho reforma --top 15
python radar.py --nicho carros --dias 14 --shorts
```
Os relatórios ficam na pasta `relatorios/`.

| Opção | O que faz | Padrão |
|---|---|---|
| `--nicho` | carros, reforma ou investimentos | carros |
| `--dias` | janela de vídeos recentes nos EUA | 30 |
| `--top` | quantos temas medir no Brasil | 20 |
| `--sementes` | quantas buscas fazer nos EUA | 10 |
| `--shorts` | incluir Shorts na análise | não |
| `--sem-ia` | não usar o Claude mesmo com a chave | – |

## Cota
A API dá 10.000 unidades por dia. Cada busca custa 100. Uma rodada padrão gasta cerca de
`(sementes + top) × 100` ≈ 3.000 unidades, então dá para rodar umas 3 vezes por dia.

## Como ler o relatório
- **Oportunidade**: demanda nos EUA (views por dia, com bônus quando canais pequenos explodem com o tema,
  sinal de que o interesse é pelo assunto e não pelo canal) × busca no Brasil × (1 − saturação no Brasil).
- **Saturação BR**: quanto os 5 maiores vídeos em português dos últimos 12 meses já somam de views.
  "Espaço livre" é onde vale correr.
- **O brasileiro também busca**: sugestões do autocompletar do YouTube; boas ideias de título.
- "conferir tradução": o termo de busca pode estar ruim; ajuste no glossário (`NICHOS` em `radar.py`).

Os vídeos dos EUA servem para estudar o assunto. O vídeo publicado deve ter roteiro próprio, adaptado ao
Brasil (preços, modelos vendidos aqui, normas), para não cair nas regras de conteúdo reutilizado.
