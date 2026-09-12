---
description: Liga o modo tutor do O.R.A.C.L.E para estudar um tópico
---

Ative o modo tutor do O.R.A.C.L.E para: $ARGUMENTS

Use a skill `oracle-tutor` e siga o contrato dela à risca.

Antes de qualquer coisa, rode:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" status
```

Se `initialized` for `false`, pare e diga ao aluno para rodar `/oracle-setup`
primeiro. Não crie o estado por conta própria.
