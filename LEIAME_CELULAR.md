# Radar no celular, sem rodar nada

O GitHub roda o radar sozinho todo dia às 6h e publica o relatório num link fixo.
No celular você só abre o link. Configuração única, uns 10 minutos (mais fácil no computador).

## 1. Criar o repositório
1. Crie uma conta grátis em https://github.com (se ainda não tiver).
2. Clique em **+ > New repository**. Nome: `radar-garagem`. Marque **Public** (o GitHub Pages
   grátis exige repositório público; o relatório não tem nada sensível e a chave fica escondida).
3. Clique em **Create repository**.

## 2. Enviar os arquivos
1. Na página do repositório, clique em **uploading an existing file** (ou **Add file > Upload files**).
2. Arraste TODO o conteúdo descompactado deste zip, incluindo a pasta `.github`.
   No Windows/Mac, pastas que começam com ponto podem ficar ocultas: ative "mostrar ocultos".
3. **Nunca envie o arquivo `radar.env`** (ele tem a sua chave). O `.gitignore` já ajuda a evitar.
4. Clique em **Commit changes**.

Confira se existe o arquivo `.github/workflows/radar.yml` no repositório. Se a pasta não subiu:
**Add file > Create new file**, digite o nome `.github/workflows/radar.yml` e cole o conteúdo do
arquivo `radar.yml` deste zip.

## 3. Guardar a chave em segredo
**Settings > Secrets and variables > Actions > New repository secret**
- Name: `YOUTUBE_API_KEY` · Secret: a sua chave
- (opcional) Name: `ANTHROPIC_API_KEY` · Secret: chave da API do Claude, para temas agrupados por IA

## 4. Ligar o site
**Settings > Pages > Build and deployment > Source: GitHub Actions**

## 5. Primeira rodada
**Actions > Radar > Run workflow** (escolha o nicho) **> Run workflow**. Leva 1 a 2 minutos.
Quando ficar verde, o link aparece no resumo da execução:
`https://SEU-USUARIO.github.io/radar-garagem/`

## No celular
- Abra o link e use **Adicionar à tela inicial** (Chrome: menu ⋮; Safari: botão compartilhar).
  Vira um ícone que abre sempre o relatório mais recente. "Histórico" mostra os anteriores.
- Para rodar na hora (ou outro nicho): app **GitHub** > repositório > **Actions > Radar > Run workflow**.
- A rodada automática é diária às 6h. Para mudar, edite a linha `cron` em `radar.yml`
  (horário em UTC: Brasília + 3h).
