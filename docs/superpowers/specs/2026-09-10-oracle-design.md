# O.R.A.C.L.E — Design

**Organized Reasoning & Academic Coaching Learning Engine**

Data: 2026-09-10
Status: aprovado, pronto para plano de implementação

## Problema

Perguntar algo ao Claude devolve a resposta. Isso resolve a dúvida e não ensina
nada. Para estudar de verdade é preciso o oposto: ser levado até a resposta,
ter o entendimento verificado, e que alguém se lembre na semana seguinte de
onde você parou e do que você já sabe.

Nenhuma das duas coisas — o método socrático e a memória entre sessões — existe
numa conversa normal com o Claude.

## O que o O.R.A.C.L.E é

Um plugin do Claude Code que, **quando explicitamente acionado**, transforma a
sessão em uma sessão de tutoria: o Claude conduz em vez de entregar, e grava o
que aconteceu num estado persistente que alimenta as sessões seguintes.

Distribuído público no GitHub. Precisa funcionar para quem não é desenvolvedor
e nunca ouviu falar de git.

### Princípio inegociável: opt-in

O modo tutor **nunca** liga sozinho. Sem `/oracle`, o Claude responde
normalmente. Uma dúvida rápida sobre algo que o usuário não quer estudar não
pode custar uma aula.

Consequência de arquitetura: o hook do plugin, com o modo desligado, não injeta
absolutamente nada.

## Escopo do v1

Dentro:

- `/oracle-setup` — escolha de storage e criação do estado
- `/oracle` e `/oracle-off` — liga/desliga o modo tutor
- `/oracle-plan` — monta plano de estudo filtrando o que o aluno já sabe
- `/oracle-status` — progresso

Fora do v1 (ver `BACKLOG.md`): explicação visual em HTML/Artifact, deep
researcher, revisão espaçada/SRS.

## Arquitetura

### Repositório do plugin

```
oracle/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── commands/
│   ├── oracle.md
│   ├── oracle-off.md
│   ├── oracle-setup.md
│   ├── oracle-plan.md
│   └── oracle-status.md
├── skills/
│   ├── oracle-setup/SKILL.md
│   ├── oracle-tutor/SKILL.md
│   ├── oracle-plan/SKILL.md
│   └── oracle-status/SKILL.md
├── hooks/
│   ├── hooks.json
│   ├── tutor-guard          # UserPromptSubmit
│   └── session-save         # SessionEnd
├── lib/
│   └── oracle-store         # única camada que toca o disco
├── tests/
├── README.md
├── BACKLOG.md
└── docs/superpowers/specs/
```

### Estado do aluno

Vive em `~/.oracle/`, fora do repositório do plugin: o código é público, o dado
é do usuário.

```
~/.oracle/
├── config.json                    # {storage_mode, version, created_at}
├── profile.json                   # objetivos, estilo de explicação que funciona
├── concepts.json                  # inventário do que o aluno sabe
├── plans/<slug>.json              # planos de estudo
├── sessions/YYYY-MM-DD-<slug>.md  # log legível de cada sessão
└── .active/<session_id>.json      # modo tutor ligado nesta sessão (efêmero)
```

Formato híbrido por decisão: **JSON** para o que é consultado por programa
(`jq`), **Markdown** para o que é lido por gente. O trilho "só pasta" tem
usuários que vão abrir esses arquivos à mão.

#### `concepts.json`

```json
[
  {
    "concept": "ponteiro em C",
    "domain": "programação/C",
    "level": "known | shaky | gap",
    "evidence": "reformulou aritmética de ponteiro corretamente em 2026-09-10",
    "updated_at": "2026-09-10"
  }
]
```

Arquivo de primeira classe, não derivado do log das sessões. É o pré-filtro:
`/oracle-plan` lê ele **antes** de montar qualquer trilha. Se estivesse
enterrado nos logs, todo plano teria que reprocessar o histórico inteiro para
descobrir o que o aluno já sabe.

#### `plans/<slug>.json`

```json
{
  "id": "slug",
  "topic": "...",
  "goal": "...",
  "deadline": "2026-10-01 | null",
  "status": "active | done | paused",
  "milestones": [
    {"title": "...", "status": "todo | doing | done", "skipped_reason": "já domina: X"}
  ],
  "sessions": ["2026-09-10-slug"],
  "created_at": "2026-09-10"
}
```

### Camada de storage

**Nenhuma skill escreve em disco diretamente.** Tudo passa por
`lib/oracle-store`, que expõe `read`, `write`, `commit` e `init`.

É isso que permite três trilhos de storage sem triplicar código — a skill não
sabe em qual trilho está:

| Trilho | `commit` faz | Para quem |
|---|---|---|
| `plain` | nada (no-op) | não sabe o que é git, só quer estudar |
| `git` | commit local | quer histórico e rollback, offline |
| `git-remote` | commit + push | quer o estado em mais de uma máquina |

`/oracle-setup` explica os três em linguagem de leigo e cria o escolhido.
Trocar de trilho depois é editar `config.json` e rodar o setup de novo.

## Fluxos

### `/oracle-setup`

Roda uma vez. Idempotente: se `~/.oracle/` já existe, mostra o estado atual e
oferece trocar de trilho — nunca sobrescreve dado.

### `/oracle [tópico]`

1. Carrega `concepts.json` e o plano ativo, se houver
2. Grava `.active/<session_id>.json`
3. Entra no contrato do tutor

Sem tópico: retoma o plano ativo, ou pergunta o que o aluno quer estudar.

### Contrato do tutor

O coração do plugin, em `skills/oracle-tutor/SKILL.md`:

1. **Diagnostica antes de explicar.** Uma ou duas perguntas para achar a borda
   do que o aluno já sabe. Explicação começa nessa borda, não do zero.
2. **Dá o próximo passo mínimo, nunca a resposta pronta.** Uma pista, uma
   pergunta que estreita o espaço, um caso menor para o aluno resolver antes.
3. **Explica por primeiro princípio mais analogia ancorada.** A analogia sai do
   que `concepts.json` diz que o aluno domina.
4. **Verifica.** O aluno reformula com as próprias palavras, ou prevê o próximo
   caso. Concordar não é entender.
5. **Fecha a sessão gravando:** coberto, onde travou, próximo passo.

### As três guardas

Sem elas o plugin vira uma prisão e é desinstalado na primeira semana.

**Escape hatch.** "me dá logo a resposta" entrega a resposta, direto, sem
sermão. O log registra que foi entregue e o conceito **não** sobe para `known`.

**O modo vale para o tópico de estudo, não para tudo.** Com o modo ligado
estudando grafos, um pedido para consertar um build quebrado é atendido
normalmente. O contrato socrático se aplica ao objeto de estudo declarado.

**`known` só por demonstração.** Um conceito sobe de nível quando o *aluno*
demonstra — reformula certo, acerta a previsão. Nunca porque o Claude explicou
bem. É a única coisa que impede `concepts.json` de virar um arquivo otimista
que corta do plano exatamente o que o aluno não sabe.

A escrita acontece no momento da demonstração, ainda durante a sessão, via
`oracle-store` — não só no fim. `session-save` é rede de segurança para o que
não foi gravado, não o único ponto de escrita: uma sessão interrompida sem
`SessionEnd` não pode apagar o progresso demonstrado.

### `/oracle-off`

Executa a mesma rotina de gravação que `session-save` e remove
`.active/<session_id>.json`. A rotina é idempotente e não faz nada quando não
há sessão ativa, então desligar à mão e depois fechar o terminal não grava o
log duas vezes.

### `/oracle-plan [tópico]`

1. Lê `concepts.json`
2. Calibra: perguntas curtas sobre o que o arquivo diz estar `known`, porque o
   inventário pode estar desatualizado ou errado
3. Monta a trilha cortando o confirmado — vira checkpoint de uma pergunta, não
   módulo — e registra `skipped_reason` em cada corte, para o aluno ver o que
   foi pulado e por quê
4. Grava em `plans/<slug>.json` e commita conforme o trilho

### Hooks

`UserPromptSubmit` → `tutor-guard`: lê `.active/<session_id>.json`. Existe,
injeta o contrato compacto; não existe, **não injeta nada**. Custo zero com o
modo desligado, que é o requisito do opt-in.

`SessionEnd` → `session-save`: se a sessão estava ativa, grava
`sessions/*.md`, atualiza `concepts.json` e o plano, commita, e remove o
arquivo de `.active/`.

O estado ativo é indexado por `session_id`, que o hook recebe no payload de
stdin: estudar num terminal e trabalhar em outro não se contaminam.

O contrato do tutor vive na SKILL.md, não no hook. A skill funciona sozinha
onde não há hooks (claude.ai, outros harnesses); o hook apenas mantém o
contrato vivo em sessão longa, evitando o drift que faz o modelo voltar a
entregar respostas prontas depois de algumas dezenas de turnos.

## Erros

| Situação | Comportamento |
|---|---|
| `~/.oracle/` não existe | Manda rodar `/oracle-setup`. Nunca cria implícito. |
| JSON corrompido | Salva `.bak`, avisa, não sobrescreve. No trilho git, oferece rollback. |
| `push` falha (offline) | Commit local permanece, avisa. Dado nunca se perde. |
| `git` ausente no trilho git | Setup detecta antes de escolher e oferece o trilho `plain`. |
| `.active/` órfão de sessão morta | `session-save` limpa entradas mais velhas que 24h. |

## Testes

- `oracle-store`: `read`/`write`/`commit`/`init` nos três trilhos
- `tutor-guard`: payload de stdin com sessão ativa, inativa e `.active/` corrompido
- `session-save`: gravação de log, atualização de conceitos, limpeza de órfãos
- `/oracle-setup`: idempotência sobre estado existente

## Decisões e alternativas descartadas

**Subagente como tutor.** Isolaria o contrato perfeitamente, mas subagente não
conversa turno a turno com o usuário — mataria o loop socrático, que é ida e
volta por natureza.

**Só skill, sem hook.** Mais simples e portável, mas o contrato drifta em
sessão longa. Resolvido mantendo o contrato na skill *e* reinjetando por hook
onde há hook.

**Postgres ou Supabase como storage.** SQL de verdade para consultas do tipo
"quais conceitos estão `shaky` neste domínio", mas exige container no ar,
migrations e credencial — inviável para a distribuição pública, cujo usuário
alvo pode não ser desenvolvedor.

**Repo remoto obrigatório.** Garantiria sync para todos ao custo de travar a
instalação de quem não tem conta no GitHub. Virou o trilho opcional
`git-remote`.
