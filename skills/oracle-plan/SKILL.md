---
name: oracle-plan
description: Use quando o aluno rodar /oracle-plan ou pedir um plano/trilha de estudo — monta a trilha filtrando o que ele já domina e grava em ~/.oracle. NÃO use durante uma sessão de tutoria em andamento (essa é a oracle-tutor).
---

# O.R.A.C.L.E — plano de estudo

O plano não começa do zero. Começa da borda do que o aluno já sabe.

## 1. Leia o inventário

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" concepts-list
```

Se o comando sair com código 2, pare e mande rodar `/oracle-setup`.

## 2. Entenda o alvo

Pergunte, se ainda não estiver claro: qual o objetivo concreto (prova,
projeto, curiosidade), qual o prazo, quanto tempo por semana. Objetivo vago
gera plano vago.

## 3. Calibre — não confie cegamente no arquivo

Para cada conceito marcado `known` que seria pré-requisito deste plano, faça
**uma** pergunta curta de verificação. O inventário pode estar desatualizado, e
cortar por engano é o pior erro possível: o aluno fica sem base e não entende
por quê.

- Confirmou: corte do plano, vire checkpoint de uma pergunta.
- Não confirmou: rebaixe o conceito e inclua no plano.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" concepts-set \
  --concept "BFS" --domain "grafos" --level shaky \
  --evidence "na calibração de 2026-09-10 não soube explicar a fila"
```

## 4. Monte a trilha

Marcos em ordem de dependência, cada um do tamanho de uma sessão. Todo marco
cortado **fica no plano** com `status: "done"` e um `skipped_reason` que diz
por quê — o aluno precisa ver o que foi pulado e poder discordar.

Grave enviando o JSON no stdin:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" plan-save <<'JSON'
{
  "topic": "Teoria dos Grafos",
  "goal": "resolver as questões de grafos da prova de 01/10",
  "deadline": "2026-10-01",
  "status": "active",
  "milestones": [
    {"title": "Representação: lista vs matriz", "status": "todo", "skipped_reason": null},
    {"title": "BFS", "status": "done", "skipped_reason": "já domina: confirmado na calibração"}
  ]
}
JSON
```

Depois:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" commit --message "oracle: plano de estudo de <tópico>"
```

## 5. Apresente

Mostre a trilha, e **diga explicitamente o que foi cortado e por quê**. Feche
dizendo que `/oracle:oracle <tópico>` começa a primeira sessão.
