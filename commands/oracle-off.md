---
description: Desliga o modo tutor e grava o log da sessão de estudo
---

Encerre a sessão de tutoria do O.R.A.C.L.E.

Antes de rodar o comando abaixo, grave o que ficou da sessão:

1. Para cada conceito que o aluno **demonstrou** ter entendido (reformulou com
   as próprias palavras, previu o próximo caso, resolveu sozinho), registre com
   `concepts-set`. Um conceito que você apenas explicou bem não vira `known`.
2. Escreva um resumo de três frases — coberto, onde travou, próximo passo — e
   grave no log da sessão:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" log --topic "<tópico>" <<'TXT'
- coberto: <o que foi visto nesta sessão>
- travou: <onde o aluno travou, ou "não travou">
- próximo passo: <o que fazer na próxima sessão>
TXT
```

Depois, feche a sessão:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_save.py" --off
```

Se a saída trouxer `"saved": false`, a sessão já estava fechada — diga isso ao
aluno e não faça nada além. Se `commit.warning` vier preenchido, repasse o
aviso.
