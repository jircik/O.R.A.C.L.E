---
name: oracle-status
description: Use quando o aluno rodar /oracle-status ou perguntar onde parou, o que já estudou ou o que vem a seguir — lê o estado do O.R.A.C.L.E e resume. NÃO use para criar ou alterar plano (essa é a oracle-plan).
---

# O.R.A.C.L.E — progresso

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" status
python3 "${CLAUDE_PLUGIN_ROOT}/lib/oracle_store.py" plan-list
```

Se `initialized` for `false`, diga só isso e mande rodar `/oracle-setup`.

Apresente, nesta ordem e sem enfeite:

1. **Plano ativo** — tópico, prazo, e quantos marcos de quantos estão `done`.
2. **Próximo marco** — o primeiro `todo` da lista. É a resposta para "o que eu
   faço agora".
3. **Última sessão** — data e tópico, lidos do `sessions/` mais recente.
4. **Domina** — os conceitos `known`, agrupados por domínio.
5. **Pendências** — conceitos `shaky` ou `gap`, que são as próximas dívidas.

Se houver mais de um plano `active`, aponte isso: provavelmente um deveria
estar `paused`. Pergunte antes de mudar qualquer coisa.

Feche sugerindo o próximo passo concreto: `/oracle <tópico do próximo marco>`.
