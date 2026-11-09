<p align="center">
  <img src="assets/banner.svg" alt="social-sim: uma estrela central cercada por personas que reagem a um anúncio" width="100%">
</p>

<h1 align="center">social-sim</h1>

<p align="center">
  <a href="https://claude.com/claude-code"><img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-Skill-D97757?style=for-the-badge&logo=claude&logoColor=white"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="SQLAlchemy 2.0" src="https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-local-003B57?style=for-the-badge&logo=sqlite&logoColor=white">
</p>

<p align="center">
  <img alt="Testes" src="https://img.shields.io/badge/testes-71_passando-2EA44F?style=flat-square&logo=pytest&logoColor=white">
  <img alt="pytest" src="https://img.shields.io/badge/pytest-8%2B-0A9EDC?style=flat-square&logo=pytest&logoColor=white">
  <img alt="Bash" src="https://img.shields.io/badge/wrapper-Bash-4EAA25?style=flat-square&logo=gnubash&logoColor=white">
  <img alt="Setuptools" src="https://img.shields.io/badge/build-setuptools-6C757D?style=flat-square&logo=python&logoColor=white">
  <img alt="Subagentes" src="https://img.shields.io/badge/subagentes-em_paralelo-D97757?style=flat-square&logo=anthropic&logoColor=white">
  <img alt="Padrão ReAct" src="https://img.shields.io/badge/padr%C3%A3o-ReAct-8A2BE2?style=flat-square">
  <img alt="Idioma" src="https://img.shields.io/badge/idioma-PT--BR-009C3B?style=flat-square">
  <img alt="Status" src="https://img.shields.io/badge/status-em_desenvolvimento-F5A623?style=flat-square">
  <a href="https://github.com/BrayanDevZN/multi-person-skill/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/BrayanDevZN/multi-person-skill?style=flat-square&logo=github"></a>
  <a href="https://github.com/BrayanDevZN/multi-person-skill/commits/main"><img alt="Último commit" src="https://img.shields.io/github/last-commit/BrayanDevZN/multi-person-skill?style=flat-square&logo=git&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://github.com/BrayanDevZN/multi-person-skill/raw/main/social-sim.zip"><img alt="Baixar o ZIP" src="https://img.shields.io/badge/%E2%AC%87_BAIXAR-social--sim.zip-D97757?style=for-the-badge"></a>
</p>

Uma skill do Claude Code que simula um público de usuários de redes sociais vendo o anúncio da sua ideia
(por exemplo, "aplicativo de dieta"). Cada persona reage por conta própria, tudo fica guardado num banco SQLite local
e você recebe uma análise com conversão, objeções, segmentos, falas representativas e recomendações.

> **Aviso:** é uma simulação feita por um modelo de linguagem, não pesquisa de mercado. Serve para levantar objeções e
> hipóteses; tende a ser mais educada e mais "razoável" que gente de verdade. Não use como prova de demanda.

## Sumário

- [Instalação rápida](#instalação-rápida)
- [Como funciona](#como-funciona)
- [Modos de uso](#modos-de-uso)
- [Exemplos de pedidos](#exemplos-de-pedidos)
- [O que sai no relatório](#o-que-sai-no-relatório)
- [Estrutura do projeto](#estrutura-do-projeto)
- [O banco de dados](#o-banco-de-dados)
- [A CLI](#a-cli)
- [Decisões de design](#decisões-de-design)
- [Limitações](#limitações)
- [Desenvolvimento](#desenvolvimento)

## Instalação rápida

Requisitos: Python 3.11+, `python3-venv`, Claude Code e acesso à rede na primeira execução (instala o SQLAlchemy).

**Opção 1: pelo ZIP pronto**

1. Baixe o [`social-sim.zip`](https://github.com/BrayanDevZN/multi-person-skill/raw/main/social-sim.zip) (fica na raiz do repositório).
2. No claude.ai, vá em Settings → Skills e faça o upload do ZIP (o `SKILL.md` fica direto em `social-sim/SKILL.md`). No Claude Code, extraia a pasta `social-sim` em `~/.claude/skills/`.
3. Peça uma simulação (veja os [exemplos](#exemplos-de-pedidos)).

**Opção 2: pelo repositório**

```bash
git clone https://github.com/BrayanDevZN/multi-person-skill.git
cd multi-person-skill
bin/socialsim init        # cria o .venv, instala as dependências e cria o banco
```

Depois abra a pasta no Claude Code.

**Usar em outro projeto:** copie `.claude/skills/social-sim/`, `bin/`, `src/` e `pyproject.toml` para a raiz dele.
Os comandos do banco rodam sempre a partir da raiz do projeto, onde fica o `bin/socialsim`.

## Como funciona

```
 ideia + anúncio
       │
       ▼
 1. pesquisa o mercado na web ──► salva os achados (research)
 2. define de 3 a 8 segmentos (inclui ao menos um hostil ou mal encaixado)
 3. propõe quantas personas (de 8 a 40), justifica e PERGUNTA a você: manter, mais ou menos?
    e se as personas podem pesquisar na web antes de reagir (opcional, desligado por padrão)
 4. só depois da sua resposta: reaproveita personas do banco
 4b. para cada persona nova, pesquisa na web gente real daquele perfil (rotina, plataformas, gírias,
    atitude com anúncios) e só então cria a persona, ancorada nesses achados
 5. abre o run  ◄── antes de qualquer agente, para sobreviver a interrupções
 6. um subagente por persona, em paralelo (lotes de até 10), ciclo ReAct
 7. valida cada resultado e tenta corrigir uma vez; se falhar, registra como failed
 8. salva tudo, fecha o run e gera o relatório com números do banco
 9. pergunta em que formato você quer o relatório (HTML, PDF ou texto) e só então o gera, com
    recomendações, melhorias e próximos passos, em reports/
       │
       ▼
 análise no chat + relatório HTML (veredito, números, segmentos, objeções, falas, recomendações)
```

Cada persona recebe o mesmo anúncio, uma plataforma sua (Instagram, TikTok, LinkedIn...) e um contexto de momento
(cansada, ocupada, entediada, irritada...) para a simulação não ficar sempre favorável. Ela raciocina em passos
`Thought → Action → Observation` (`open_app`, `scroll_feed`, `view_ad`, `read_comments`, `click_ad`, `like`,
`comment`, `share`, `hide_ad`...) e devolve **um único JSON**:

```json
{
  "action": "ignore | like | comment | share | click | convert | reject",
  "sentiment": "positive | neutral | negative",
  "purchase_intent": 0,
  "comment": null,
  "objections": ["short phrases"],
  "react_trace": "Thought: ...\nAction: ...\nObservation: ..."
}
```

Regras de consistência checadas pelo orquestrador:

| Ação | Exigência |
|---|---|
| `convert` | `purchase_intent` ≥ 7 e sentimento não negativo |
| `reject` | sentimento negativo e `purchase_intent` ≤ 3 |
| `ignore` | `purchase_intent` ≤ 4 e `comment` nulo |
| `comment` | `comment` obrigatório; nulo quando a persona não escreveu nada |

A persona também nunca pode dizer que é uma IA ou uma simulação.

### Personas que pesquisam (opcional)

Por padrão a persona reage só com o anúncio, a memória e o resumo de mercado. Se você ativar o **modo pesquisa**, cada
agente de persona ganha a mesma ferramenta de busca na web (`WebSearch`) que o agente principal usa, mas **só pesquisa se
aquela pessoa realmente procuraria algo** (o preço, avaliações, a empresa, uma alternativa mais barata). Não é obrigatório:
a maioria só dá scroll. São no máximo 2 buscas, escritas como a pessoa digitaria, e o que ela encontrou aparece no
`react_trace` e pode mudar a decisão. Fica mais realista, porém mais lento e mais caro.

## Modos de uso

| Você diz... | Modo | O que acontece |
|---|---|---|
| Só dá a ideia (e talvez o anúncio) | **Autônomo** (padrão) | Pesquisa, propõe segmentos e quantidade, **espera a sua aprovação** (manter, aumentar ou diminuir), então cria personas, simula todas e analisa |
| Descreve personas ou nomeia as salvas | **Manual** | Sem pesquisa e sem planejar o público: faz exatamente o pedido |
| Quer continuar uma rodada interrompida | **Retomada** | `run resume` e simula só as personas pendentes ou que falharam |
| Pergunta sobre resultados antigos | **Consulta** | Usa relatórios e listas, sem simular |

## Exemplos de pedidos

```
simula um aplicativo de dieta com usuários de redes sociais
cria 5 personas de enfermeiras de plantão noturno e testa o app de dieta nelas
continua a simulação do app de dieta, algumas personas falharam
quem rejeitou o app de dieta e por quê?
simula com 15 personas esse anúncio: "Emagreça sem contar calorias. Teste grátis."
```

## O que sai no relatório

Depois que todas as personas respondem, o agente principal **pergunta em que formato você quer o relatório** (você marca **HTML**, **PDF** ou **texto**, podendo escolher mais de um), escreve a análise no chat e gera o arquivo em `reports/`: `run_<id>.html` (abre em qualquer navegador, funciona offline, tema claro e escuro), `run_<id>.pdf` (precisa de Chrome ou Chromium instalado) ou `run_<id>.md` (texto simples). Os números, gráficos, tabela de
segmentos, objeções e cartões de cada persona vêm do banco; o texto (veredito, recomendações, melhorias no anúncio, sugestão
de novo anúncio, riscos e próximos passos) vem da análise do agente.

Conteúdo da análise:

1. **Veredito:** como o público recebeu a ideia, em duas ou três frases.
2. **Números:** personas simuladas, taxa de conversão, taxa de engajamento, intenção média de compra e falhas.
3. **Por segmento:** quem respondeu melhor e pior.
4. **Principais objeções:** ranqueadas, com contagem e interpretação.
5. **Vozes:** três a cinco falas representativas, ao menos uma negativa.
6. **Recomendações:** mudanças concretas no anúncio e no produto.
7. **Ressalvas:** limites da simulação e personas que falharam.
8. **Referência:** id da ideia e do run, e como refazer ou retomar.

Todos os números vêm do `report run`, nunca de estimativa do modelo.

## Estrutura do projeto

```
.
├── .claude/skills/social-sim/
│   ├── SKILL.md                  # entrada da skill: modos e regras inegociáveis
│   └── prompts/
│       ├── orchestrator.md       # manual de operação: fluxo, validação, relatório
│       ├── cli_reference.md      # referência exata dos comandos do banco
│       ├── persona_generator.md  # template para criar personas
│       └── persona_agent.md      # template do subagente de cada persona
├── bin/socialsim                 # wrapper: cria o .venv e instala dependências na 1ª execução
├── src/socialsim/                # CLI + modelos SQLAlchemy
│   ├── cli.py, core.py, db.py, models.py, registry.py, validation.py, report_html.py
│   └── commands/                 # ideas, personas, runs, admin
├── tests/                        # pytest (71 testes)
├── data/socialsim.db             # banco local, criado automaticamente, fora do git
├── reports/run_<id>.{html,pdf,md} # relatórios gerados, fora do git
├── assets/banner.svg             # banner animado deste README
└── social-sim.zip                # projeto empacotado, pronto para usar
```

## O banco de dados

SQLite via SQLAlchemy, em `data/socialsim.db`. Mude o caminho com a variável `SOCIALSIM_DB` ou a flag `--db`.

| Tabela | Guarda |
|---|---|
| `ideas` | nome, descrição e texto do anúncio de cada ideia testada |
| `research` | achados da pesquisa de mercado, com a fonte |
| `personas` | perfil, personalidade, segmento, plataformas e tags; são permanentes |
| `persona_state` | memória do que a persona já viu, para reagir com fadiga, confiança ou comparação |
| `runs` | cada rodada de simulação e seu status (`running`, `partial`, `completed`) |
| `reactions` | o resultado de cada persona em cada run, incluindo o `react_trace` |

## A CLI

Todas as operações passam por `bin/socialsim`. A entrada é JSON (`--json` ou `--file`) e a saída é sempre uma linha
JSON: `{"ok": true, "data": ...}` ou `{"ok": false, "error": ..., "hint": ...}`.

| Grupo | Comandos |
|---|---|
| Administração | `init`, `schema`, `stats`, `query`, `export`, `commands` |
| Ideias | `idea create \| get \| list \| update \| delete` |
| Pesquisa | `research add \| list \| delete` |
| Personas | `persona create \| get \| list \| search \| update \| delete` |
| Estado | `state get \| update` |
| Rodadas | `run start \| status \| finish \| list \| resume \| delete` |
| Reações | `reaction save \| get \| list \| delete` |
| Relatório | `report run \| html \| pdf \| text` |

```bash
bin/socialsim commands                 # catálogo completo com campos e exemplos
bin/socialsim persona list --json '{"min_age": 30, "tag": "lote-1"}'
bin/socialsim report run 1
bin/socialsim report html 1 --out reports/run_1.html --file analise.json
bin/socialsim query --sql "SELECT segment, COUNT(*) n FROM personas GROUP BY segment"
```

`persona search` devolve `likely_duplicate` para evitar personas repetidas. `query` aceita só `SELECT`/`WITH`.
Referência completa: [`cli_reference.md`](.claude/skills/social-sim/prompts/cli_reference.md).

## Decisões de design

- **Só o orquestrador escreve no banco.** Os subagentes não têm ferramentas: devolvem JSON e pronto. Uma falha de
  agente não corrompe dados.
- **Personas pesquisadas, não inventadas.** Antes de criar cada persona nova, a skill pesquisa na web como é a vida de gente real daquele perfil e salva os achados no banco (`research`), então dá para auditar a origem de cada persona.
- **Confirmação antes de gastar.** Depois da pesquisa, a skill mostra o plano (segmentos, número de personas, custo em subagentes) e só segue quando você aprova, aumenta ou diminui. Dizer "faz direto" ou fixar um número pula a pergunta.
- **O run abre antes dos agentes**, então o progresso sobrevive a interrupções e pode ser retomado.
- **Contra o viés de "educação" do modelo:** ignorar é o resultado padrão, há contextos ruins de propósito, todo
  público inclui segmentos hostis e o resumo de mercado nunca traz conclusões sobre o produto.
- **Relatório com números do banco.** O HTML é gerado pela CLI: o agente só escreve o texto, e a página se recusa a sair enquanto houver persona pendente.
- **Nenhuma análise com resultado parcial.** Só depois que todos os agentes voltam ou são marcados como falhos.
- **Os testes checam os prompts contra a CLI:** todo comando citado nos prompts precisa existir e todo exemplo de
  JSON precisa passar na validação.

## Limitações

- Custo alto de tokens em rodadas grandes: 40 personas são 40 subagentes mais a pesquisa.
- As personas podem convergir para reações parecidas mesmo com perfis diferentes; o relatório avisa, mas não corrige.
- A variedade depende em parte do contexto de sessão que o orquestrador inventa para cada persona.
- A simulação completa com um modelo real ainda não foi testada de ponta a ponta; ajuste os prompts com base nos
  primeiros resultados reais.

## Desenvolvimento

```bash
bin/socialsim init                       # cria o .venv e o banco
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest               # 71 testes
```

Para gerar o ZIP de novo depois de mudar algo:

```bash
scripts/build_skill_zip.sh
```
