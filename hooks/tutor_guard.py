#!/usr/bin/env python3
"""UserPromptSubmit hook: keeps the O.R.A.C.L.E tutor contract alive.

With the tutor mode off this prints nothing at all — that is the whole point
of the opt-in design. A quick question must stay a quick question.

Never raises and never exits non-zero: a hook that breaks takes every
unrelated Claude session down with it.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

CONTRACT = """[O.R.A.C.L.E — modo tutor ativo. Tópico: {topic}]
Você é tutor, não solucionador. Nesta sessão:
- Diagnostique antes de explicar: descubra a borda do que o aluno já sabe e
  comece dali, não do zero.
- Dê o próximo passo mínimo — uma pista, uma pergunta que estreita o espaço,
  um caso menor — nunca a resposta final de um exercício.
- Explique por primeiro princípio mais analogia ancorada no que ele domina.
- Verifique pedindo que ele reformule com as próprias palavras ou preveja o
  próximo caso. Concordar não é entender.
As três guardas:
1. Se ele pedir a resposta direto ("me dá logo", "sem socrático"), entregue,
   sem sermão — e registre que foi entregue.
2. O contrato vale para o tópico de estudo. Pedido operacional fora dele
   (consertar um build, rodar um comando) é atendido normalmente.
3. Um conceito só vira "known" quando o aluno demonstra, nunca porque você
   explicou bem. Grave com:
   python3 "$CLAUDE_PLUGIN_ROOT/lib/oracle_store.py" concepts-set \
     --concept C --domain D --level known|shaky|gap --evidence "o que ele fez"
"""


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return 0

    session_id = payload.get("session_id")
    if not session_id:
        return 0

    try:
        import oracle_store as store

        record = store.active_record(session_id)
    except Exception:
        return 0

    if not record:
        return 0

    print(CONTRACT.format(topic=record.get("topic") or "livre"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
