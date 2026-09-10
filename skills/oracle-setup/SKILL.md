---
name: oracle-setup
description: Use quando o aluno rodar /oracle-setup, ou quando qualquer comando do O.R.A.C.L.E reclamar que o estado não existe — escolhe um dos três trilhos de armazenamento e cria ~/.oracle. NÃO use para trocar dados de um plano de estudo já existente.
---

# O.R.A.C.L.E — configuração do armazenamento

Seu interlocutor pode não ser desenvolvedor. Não presuma que ele sabe o que é
git, repositório ou commit.

## 1. Veja o que já existe

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" status
```

Se `initialized` já for `true`, **não recrie nada**. Diga em que trilho ele
está hoje e pergunte se quer trocar. Trocar de trilho preserva os dados.

## 2. Ofereça os três trilhos, nesta linguagem

**1 — Só uma pasta** (`plain`)
Seus planos e seu progresso ficam numa pasta no computador. Simples, funciona
sem internet, não precisa de conta em lugar nenhum. **Escolha esta se você não sabe o que é git**
ou se só quer estudar sem configurar nada.

**2 — Pasta com histórico** (`git`)
Igual à anterior, mais um histórico de tudo que mudou: dá para ver como seu
plano evoluiu e voltar atrás se algo for escrito errado. Precisa do `git`
instalado. Continua tudo no seu computador, nada sai dele.

**3 — Pasta com histórico e cópia online** (`git-remote`)
Igual à 2, e ainda envia uma cópia para um repositório privado seu no GitHub,
para estudar em mais de um computador. Precisa de conta no GitHub configurada.

Se `git` não estiver instalado na máquina, diga isso e ofereça só o trilho 1.
Verifique com `command -v git`.

## 3. Crie

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" init --mode <plain|git|git-remote>
```

No trilho 3, depois do `init`, peça a URL do repositório privado dele e
configure o remoto:

```bash
git -C "$HOME/.oracle" remote add origin <url>
git -C "$HOME/.oracle" push -u origin HEAD
```

Se ele não tiver um repositório ainda e tiver o `gh` instalado e autenticado,
ofereça criar: `gh repo create <nome> --private --source "$HOME/.oracle" --push`.
Avise que o repositório precisa ser **privado** — é o histórico de estudo dele.

## 4. Feche

Diga onde ficou o estado (o `home` do `status`), e que os próximos passos são
`/oracle-plan` para montar um plano ou `/oracle <tópico>` para estudar agora.
