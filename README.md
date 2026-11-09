# multi-person-skill

Uma skill do Claude Code que simula vários usuários de redes sociais vendo o anúncio de uma ideia (por exemplo,
"aplicativo de dieta"), guarda cada persona, o estado dela e o feedback num banco SQLite local, e devolve uma análise.

> É uma simulação feita por um modelo de linguagem, não pesquisa de mercado. Ela é boa para levantar objeções e
> hipóteses; tende a ser mais educada e mais "razoável" que gente de verdade. Não use como prova de demanda.

## Como funciona

1. Você dá uma ideia (e, se quiser, o texto do anúncio).
2. **Modo padrão (autônomo):** o Claude pesquisa o mercado na web, define os segmentos de público, decide quantas
   personas criar (entre 8 e 40), reaproveita as que já estão no banco e cria só as que faltam.
3. Cada persona é simulada por um subagente próprio, em paralelo (lotes de até 10), com um ciclo ReAct
   (Thought → Action → Observation) de uso da rede social.
4. Só quando **todas** terminam, o Claude grava os resultados e entrega a análise: conversão, objeções,
   segmentos, falas representativas e recomendações.

Outros modos: **manual** (você descreve as personas ou escolhe quais usar), **retomada** (continua uma rodada
interrompida) e **consulta** (perguntas sobre resultados antigos).

## Uso

Com o projeto aberto no Claude Code, a skill `social-sim` é descoberta sozinha. Exemplos:

```
simula um aplicativo de dieta com usuários de redes sociais
cria 5 personas de enfermeiras de plantão noturno e testa o app de dieta nelas
continua a simulação do app de dieta, algumas personas falharam
quem rejeitou o app de dieta e por quê?
```

## Estrutura

```
.claude/skills/social-sim/
├── SKILL.md                   # entrada da skill: modos e regras
└── prompts/                   # orquestrador, subagente de persona, gerador de personas, referência da CLI
bin/socialsim                  # wrapper: cria o .venv e instala dependências na primeira execução
src/socialsim/                 # CLI + modelos SQLAlchemy
tests/                         # pytest
data/socialsim.db              # banco local (criado automaticamente, fora do git)
```

## O banco

SQLite via SQLAlchemy. Tabelas: `ideas`, `research`, `personas`, `persona_state`, `runs`, `reactions`.
Personas são permanentes e lembram o que já viram. Caminho padrão: `data/socialsim.db`; mude com a variável
`SOCIALSIM_DB` ou a flag `--db`.

## A CLI

Todas as operações passam por `bin/socialsim`. A entrada é JSON (`--json` ou `--file`) e a saída é sempre uma linha
JSON: `{"ok": true, "data": ...}` ou `{"ok": false, "error": ..., "hint": ...}`.

```
bin/socialsim commands                 # catálogo completo dos comandos e campos
bin/socialsim persona list --json '{"min_age": 30, "tag": "lote-1"}'
bin/socialsim report run 1
bin/socialsim query --sql "SELECT segment, COUNT(*) n FROM personas GROUP BY segment"
```

Referência completa: `.claude/skills/social-sim/prompts/cli_reference.md`.

## Desenvolvimento

Requer Python 3.11+ e acesso à rede na primeira execução (instala o SQLAlchemy).

```
bin/socialsim init                     # cria o .venv e o banco
.venv/bin/python -m pytest             # roda os testes
```

Os testes cobrem a CLI e também a consistência dos prompts com ela: todo comando citado nos prompts precisa existir
e todo exemplo de JSON precisa passar na validação.

## Status

Banco, CLI, testes e prompts estão prontos. A simulação completa com um modelo real **ainda não foi testada de
ponta a ponta**; os prompts devem ser ajustados com base nos primeiros resultados reais.
