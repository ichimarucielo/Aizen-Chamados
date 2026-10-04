"""Gera uma cópia LIMPA do dicionário; o YAML original não é alterado.

Uso (raiz do projeto):  python limpar_yaml.py [yaml_original] [yaml_saida]
Padrão de saída:        <nome>.limpo.yaml, ao lado do original.
Corrige o que a primeira versão do evoluir_dicionario.py deixou: padrões na intenção
errada, 'ajuste no boleto' e textos 'quando' trocados. Idempotente e determinístico.
"""
import sys
from pathlib import Path

import yaml

DEFAULT = Path("data/input/dicionario_aizen_intencoes.yaml")

# padrões que ficaram colados na intenção errada (o dono certo já os tem)
REMOVER = {
    "INT_NF_CANCEL_REEMISSAO": [
        "aumento no prazo para pagamento", "aumento no prazo de pagamento",
        "aumentar prazo de pagamento", "atualizado para a data de vencimento",
        "vencimento corrigido", "qual o prazo cadastrado", "conste + po + corrigir",
        "cobranças indevidas", "mínimo mensal + indevidas",
        "solicito o cancelamento do mesmo + contrato",
    ],
    "INT_PAG_BOLETO_REENVIO": ["ajuste no boleto"],  # amplo demais (era alteração de vencimento)
}


def limpar(d: dict) -> list[str]:
    log = []
    por_id = {i["id"]: i for i in d["intencoes"]}
    for iid, padroes in REMOVER.items():
        atuais = por_id[iid]["padroes"]
        for p in padroes:
            if p in atuais:
                atuais.remove(p)
                log.append(f"removido de {iid}: {p!r}")

    # o texto 'quando' da regra de NF ficou na regra de contrato; restaura cada um no seu lugar
    for r in d["precedencia"]:
        if r["preferir"] == "INT_NF_CANCEL_REEMISSAO" and "INT_COB_CONTESTACAO" in r["sobre"]:
            novo = "Há pedido explícito de cancelar, substituir ou reemitir NF; cobrança, contrato, CNPJ, desconto e PO podem ser contexto."
        elif r["preferir"] == "INT_PAG_VENCIMENTO":
            novo = "O pedido é mudar a data/prazo; reenviar boleto é só o meio."
        elif r["preferir"] == "INT_CON_CANCELAMENTO":
            novo = "O objeto cancelado é o contrato; NF aparece só como contexto."
        else:
            continue
        if r.get("quando") != novo:
            r["quando"] = novo
            log.append(f"'quando' ajustado: {r['preferir']}")
    return log


if __name__ == "__main__":
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else origem.with_name(f"{origem.stem}.limpo{origem.suffix}")
    if saida.resolve() == origem.resolve():
        sys.exit("A saída não pode ser o próprio original.")
    dic = yaml.safe_load(origem.read_text(encoding="utf-8"))
    log = limpar(dic)
    saida.write_text(yaml.safe_dump(dic, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print("\n".join(log) if log else "Nada a limpar (cópia idêntica em conteúdo).")
    print(f"Original intacto: {origem}\nCópia limpa:     {saida}")