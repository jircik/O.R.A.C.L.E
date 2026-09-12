# O.R.A.C.L.E

**Organized Reasoning & Academic Coaching Learning Engine**

Um mentor de estudos para o Claude Code. Ele ensina em vez de entregar a
resposta, e lembra do que você já sabe entre uma sessão e outra.

Só liga quando você pede. Sem `/oracle:oracle`, o Claude responde normalmente
— uma dúvida rápida continua uma dúvida rápida.

## Instalação

Este repositório ainda não está publicado no GitHub — instale a partir de uma
cópia local:

```text
/plugin marketplace add /caminho/para/oracle
/plugin install oracle
/oracle:oracle-setup
```

Para só experimentar, sem instalar de fato:

```bash
claude --plugin-dir /caminho/para/oracle
```

Quando o repositório for publicado, a instalação passa a ser:

```text
/plugin marketplace add jircik/oracle
/plugin install oracle
/oracle:oracle-setup
```

O `/oracle:oracle-setup` pergunta onde guardar seus planos e seu progresso.
São três opções, e a primeira não exige saber nada de git.

## Comandos

| Comando | O que faz |
|---|---|
| `/oracle:oracle-setup` | Escolhe onde guardar seus dados e cria o estado |
| `/oracle:oracle <tópico>` | Liga o modo tutor e começa a estudar |
| `/oracle:oracle-off` | Encerra a sessão e grava o que aconteceu |
| `/oracle:oracle-plan <tópico>` | Monta uma trilha, pulando o que você já domina |
| `/oracle:oracle-status` | Onde você parou e o que vem a seguir |

O Claude Code também aceita uma forma mais curta, sem o prefixo `oracle:`,
para alguns desses comandos — se você vir `/oracle-status` funcionar sozinho,
é isso.

## Como ele ensina

Diagnostica antes de explicar, dá o próximo passo mínimo em vez da resposta,
explica por primeiro princípio com analogias ancoradas no que você já sabe, e
verifica pedindo que você reformule.

Três guardas impedem isso de virar uma prisão:

- **Você pode pedir a resposta.** "Me dá logo" entrega, sem sermão.
- **O modo vale para o tópico de estudo.** Consertar um build no meio da
  sessão continua funcionando normalmente.
- **Um conceito só conta como sabido quando você demonstra** — nunca porque o
  Claude explicou bem.

## Onde ficam seus dados

Em `~/.oracle/`, na sua máquina. Nada é enviado para lugar nenhum, a menos que
você escolha o trilho com cópia no seu repositório privado.

## Desenvolvimento

```bash
python3 -m unittest discover -s tests -v
```

Sem dependências: Python 3.9+ e a biblioteca padrão.

## Backlog

Explicação visual em HTML, deep researcher e revisão espaçada estão em
[`BACKLOG.md`](BACKLOG.md).
