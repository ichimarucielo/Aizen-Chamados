"""Evolui o dicionário AIZEN de forma idempotente e segura.

Uso:
    python evoluir_dicionario.py [caminho_do_yaml]

Características:
- não duplica padrões, intenções, precedências ou exceções;
- cria backup com timestamp antes de alterar o arquivo;
- preserva a ordem existente do YAML;
- não altera conteúdo existente;
- valida estrutura, IDs e as 6 classificações permitidas;
- grava de forma atômica para evitar corrupção do YAML.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from shutil import copy2

import yaml


DEFAULT = Path("data/input/dicionario_aizen_intencoes.yaml")


# ---------------------------------------------------------------------------
# NOVOS PADRÕES
# ---------------------------------------------------------------------------

PADROES: dict[str, list[str]] = {
    "INT_NF_CANCEL_REEMISSAO": [
        "cancelar nf",
        "cancelar e emitir",
        "emitir uma nova nf",
        "cancelar a nota",
        "cancelar as nf",
        "cancelamento dessa nf",
        "nf + ser canceladas",
        "substituição de nf",
        "substituição de todas as nf",
    ],
    "INT_NF_DATA_EMISSAO": [
        "emissão no final do mês",
        "emitidas no final do mês",
    ],
    "INT_PAG_VENCIMENTO": [
        "aumento no prazo para pagamento",
        "aumento no prazo de pagamento",
        "aumentar prazo de pagamento",
        "atualizado para a data de vencimento",
        "vencimento corrigido",
        "prorrogação da nf",
        "prorrogação de boleto",
        "data de vencimento atualizada",
    ],
    "INT_PAG_FINANCEIRO": [
        "qual o prazo cadastrado",
        "bloqueio por inadimplência",
        "levantamento de todos os pagamentos",
    ],
    "INT_PAG_BOLETO_REENVIO": [
        "preciso do boleto",
        "ajuste no boleto",
    ],
    "INT_PAG_CONTA": [
        "trocar a conta bancária",
        "mudando a forma de pagamento",
    ],
    "INT_COB_CONTESTACAO": [
        "cobranças indevidas",
        "mínimo mensal + indevidas",
        "valores indevidos",
        "cobrança incorreta",
        "divergência de valores",
        "divergência entre o valor",
        "volumetria cobrada",
        "volume cobrado",
        "divergência + transações",
        "valor da nf + discrepante",
        "entender o motivo do aumento",
        "mais que dobrado",
        "constatei diferenças",
        "não conseguimos localizar + transações",
        "esclarecer ao que se refere a cobrança",
        "transações que estamos cobrando",
        "valor está incorreto",
    ],
    "INT_COB_DUPLICIDADE": [
        "cobrada em duplicidade",
        "cobradas em duplicidade",
        "cobranças duplicadas",
    ],
    "INT_COB_SETUP": [
        "cobrança de chave de loja",
        "chaves de loja + custo",
    ],
    "INT_FAT_DUVIDA": [
        "confirmar o valor correto para pagamento",
        "quais mids + cobrança",
        "nunca foi cobrado",
        "não está sendo cobrado",
        "está sem cobrança",
        "não localizei nenhuma nf",
        "duas nf + nf válida",
        "duas nf + corretas",
    ],
    "INT_FAT_CORRECAO_PO": [
        "conste + po + corrigir",
        "erro no descritivo dos serviços",
    ],
    "INT_CON_CANCELAMENTO": [
        "solicito o cancelamento do mesmo + contrato",
        "cancelamento do serviço",
        "cancelar contrato",
        "cancelamento do contrato",
    ],
    "INT_CON_CADASTRO": [
        "lista de recebimento",
        "incluir o email",
        "incluir email",
        "encaminhar as faturas + email",
    ],
    "INT_CON_CONDICOES": [
        "renovação contratual",
        "novo termo de adesão",
    ],
    "INT_ADM_DOCUMENTOS": [
        "histórico de reajustes",
        "histórico completo dos reajustes",
    ],
    "INT_ADM_ACESSO": [
        "não consigo consultar a parte financeira",
    ],
}


# ---------------------------------------------------------------------------
# NOVAS INTENÇÕES
# ---------------------------------------------------------------------------
#
# Não criamos intenção genérica de "Correção de NF":
# o histórico ainda não sustenta uma intenção ampla o suficiente para isso.
#

NOVAS_INTENCOES: list[dict] = []


# ---------------------------------------------------------------------------
# PRECEDÊNCIA
# ---------------------------------------------------------------------------

PRECEDENCIA: list[dict] = [
    {
        "preferir": "INT_PAG_VENCIMENTO",
        "sobre": [
            "INT_PAG_BOLETO_REENVIO",
            "INT_PAG_FINANCEIRO",
        ],
        "quando": "O pedido é mudar a data/prazo; reenviar boleto é só o meio.",
    },
    {
        "preferir": "INT_CON_CANCELAMENTO",
        "sobre": [
            "INT_NF_CANCEL_REEMISSAO",
        ],
        "quando": "O objeto cancelado é o contrato; NF aparece só como contexto.",
    },
    {
        "preferir": "INT_NF_CANCEL_REEMISSAO",
        "sobre": [
            "INT_FAT_REENVIO_NF",
        ],
        "quando": "Pede cancelar e emitir nova NF, não apenas reenviar.",
    },
]


# ---------------------------------------------------------------------------
# EXCEÇÕES / CONFLITOS HISTÓRICOS
# ---------------------------------------------------------------------------

EXCECOES: list[dict] = [
    {
        "id": "valor_nf_contestar_vs_verificar",
        "causa_ou_rotulo": "Dúvida/divergência de valor da NF ou transações",
        "regra": (
            "Histórico: contestar/questionar valor, volume ou transações cobradas "
            "=> Cobrança e Contestação; confirmar qual NF é válida, duas NFs recebidas, "
            "valor correto para pagar ou MIDs cobrados "
            "=> Faturamento e Obrigações Fiscais."
        ),
    },
    {
        "id": "sem_cobranca_dividido",
        "causa_ou_rotulo": "Cliente ativo sem cobrança",
        "exemplos_chamado": [
            "17839281",
            "25276254",
        ],
        "regra": (
            "Histórico dividido entre Faturamento e Contratos. "
            "O dicionário adota Faturamento porque a ação principal é verificar o faturamento."
        ),
    },
    {
        "id": "rotulos_template_divergentes",
        "causa_ou_rotulo": (
            "Rótulo do template diverge da ação pedida no corpo"
        ),
        "exemplos_chamado": [
            "19985167",
            "20314174",
            "23831268",
            "25498504",
            "25974810",
            "27052744",
            "27749029",
        ],
        "regra": (
            "A classificação decorre da ação pedida no corpo do chamado; "
            "nesses chamados o rótulo histórico não deve ser usado como evidência única."
        ),
    },
]


# ---------------------------------------------------------------------------
# UTILITÁRIOS
# ---------------------------------------------------------------------------

def _adicionar_unicos(destino: list, novos: list) -> int:
    """Adiciona somente itens ainda ausentes e retorna a quantidade adicionada."""
    adicionados = 0

    for item in novos:
        if item not in destino:
            destino.append(item)
            adicionados += 1

    return adicionados


def _backup(caminho: Path) -> Path:
    """Cria backup versionado antes da alteração."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = caminho.with_name(
        f"{caminho.stem}.yaml.bak_{timestamp}"
    )
    copy2(caminho, backup)
    return backup


def _validar_estrutura(d: dict) -> None:
    """Valida a estrutura mínima esperada do dicionário."""
    if not isinstance(d, dict):
        raise ValueError("O YAML raiz precisa ser um objeto/dicionário.")

    classes_permitidas = d.get("classes_permitidas")
    if not isinstance(classes_permitidas, list):
        raise ValueError("`classes_permitidas` precisa ser uma lista.")

    intencoes = d.get("intencoes")
    if not isinstance(intencoes, list):
        raise ValueError("`intencoes` precisa ser uma lista.")

    ids: set[str] = set()

    for item in intencoes:
        if not isinstance(item, dict):
            raise ValueError("Cada intenção precisa ser um objeto.")

        campos_obrigatorios = (
            "id",
            "intencao",
            "causa_padrao",
            "classificacao",
            "padroes",
        )

        faltantes = [
            campo
            for campo in campos_obrigatorios
            if campo not in item
        ]

        if faltantes:
            raise ValueError(
                f"Intenção inválida {item.get('id')!r}; "
                f"campos ausentes: {faltantes}"
            )

        iid = item["id"]

        if not isinstance(iid, str) or not iid.strip():
            raise ValueError("Toda intenção precisa possuir um `id` válido.")

        if iid in ids:
            raise ValueError(f"ID de intenção duplicado: {iid}")

        ids.add(iid)

        if item["classificacao"] not in classes_permitidas:
            raise ValueError(
                f"Classe fora do contrato: {iid} -> "
                f"{item['classificacao']!r}"
            )

        if not isinstance(item["padroes"], list):
            raise ValueError(
                f"`padroes` precisa ser lista: {iid}"
            )

        for padrao in item["padroes"]:
            if not isinstance(padrao, str) or not padrao.strip():
                raise ValueError(
                    f"Padrão inválido em {iid}: {padrao!r}"
                )


def _validar_causas(d: dict) -> None:
    """Garante que uma causa padrão não pertença a duas classes."""
    causa_classe: dict[str, str] = {}

    for intencao in d["intencoes"]:
        causa = intencao["causa_padrao"]
        classificacao = intencao["classificacao"]

        anterior = causa_classe.get(causa)

        if anterior is None:
            causa_classe[causa] = classificacao
            continue

        if anterior != classificacao:
            raise ValueError(
                "A mesma causa padrão aponta para duas classes: "
                f"{causa!r} -> {anterior!r} / {classificacao!r}"
            )


def _validar_precedencia(d: dict) -> None:
    """Garante que precedências apontem para intenções existentes."""
    intencao_ids = {item["id"] for item in d["intencoes"]}

    for regra in d.get("precedencia", []):
        preferir = regra.get("preferir")
        sobre = regra.get("sobre", [])

        if preferir not in intencao_ids:
            raise ValueError(
                f"Precedência aponta para intenção inexistente: {preferir}"
            )

        for alvo in sobre:
            if alvo not in intencao_ids:
                raise ValueError(
                    f"Precedência aponta para intenção inexistente: {alvo}"
                )


def _validar_excecoes(d: dict) -> None:
    """Garante IDs únicos nas exceções."""
    excecoes = d.get("conflitos_e_excecoes", [])

    if not isinstance(excecoes, list):
        raise ValueError(
            "`conflitos_e_excecoes` precisa ser uma lista."
        )

    ids: set[str] = set()

    for item in excecoes:
        if not isinstance(item, dict):
            raise ValueError(
                "Cada conflito/exceção precisa ser um objeto."
            )

        iid = item.get("id")

        if not isinstance(iid, str) or not iid.strip():
            raise ValueError(
                "Toda exceção precisa possuir um `id` válido."
            )

        if iid in ids:
            raise ValueError(
                f"ID de exceção duplicado: {iid}"
            )

        ids.add(iid)


def validar(d: dict) -> None:
    """Executa todas as validações do dicionário."""
    _validar_estrutura(d)
    _validar_causas(d)
    _validar_precedencia(d)
    _validar_excecoes(d)


# ---------------------------------------------------------------------------
# APLICAÇÃO
# ---------------------------------------------------------------------------

def aplicar(d: dict) -> dict[str, int]:
    """Aplica a evolução do dicionário de maneira idempotente."""
    validar(d)

    por_id = {
        item["id"]: item
        for item in d["intencoes"]
    }

    padroes_adicionados = 0

    for intencao_id, novos_padroes in PADROES.items():
        if intencao_id not in por_id:
            raise ValueError(
                f"Intenção inexistente para receber padrões: {intencao_id}"
            )

        atuais = por_id[intencao_id].setdefault("padroes", [])

        padroes_adicionados += _adicionar_unicos(
            atuais,
            novos_padroes,
        )

    intencoes_adicionadas = 0

    for nova in NOVAS_INTENCOES:
        iid = nova["id"]

        if iid in por_id:
            continue

        d["intencoes"].append(nova)
        por_id[iid] = nova
        intencoes_adicionadas += 1

    precedencias = d.setdefault("precedencia", [])

    precedencias_adicionadas = 0

    for regra in PRECEDENCIA:
        existe = any(
            atual.get("preferir") == regra["preferir"]
            and atual.get("sobre") == regra["sobre"]
            for atual in precedencias
        )

        if not existe:
            precedencias.append(regra)
            precedencias_adicionadas += 1

    excecoes = d.setdefault(
        "conflitos_e_excecoes",
        [],
    )

    ids_excecoes = {
        item["id"]
        for item in excecoes
        if isinstance(item, dict) and "id" in item
    }

    excecoes_adicionadas = 0

    for excecao in EXCECOES:
        if excecao["id"] in ids_excecoes:
            continue

        excecoes.append(excecao)
        ids_excecoes.add(excecao["id"])
        excecoes_adicionadas += 1

    validar(d)

    return {
        "intencoes_adicionadas": intencoes_adicionadas,
        "padroes_adicionados": padroes_adicionados,
        "precedencias_adicionadas": precedencias_adicionadas,
        "excecoes_adicionadas": excecoes_adicionadas,
    }


# ---------------------------------------------------------------------------
# ESCRITA SEGURA
# ---------------------------------------------------------------------------

def salvar_atomicamente(caminho: Path, d: dict) -> None:
    """Escreve o YAML em arquivo temporário e substitui o original."""
    temporario = caminho.with_name(
        f"{caminho.name}.tmp"
    )

    conteudo = yaml.safe_dump(
        d,
        allow_unicode=True,
        sort_keys=False,
        width=120,
        default_flow_style=False,
    )

    temporario.write_text(
        conteudo,
        encoding="utf-8",
    )

    temporario.replace(caminho)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    caminho = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else DEFAULT
    )

    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo YAML não encontrado: {caminho}"
        )

    if caminho.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(
            f"Arquivo informado não parece ser YAML: {caminho}"
        )

    try:
        dicionario = yaml.safe_load(
            caminho.read_text(encoding="utf-8")
        )
    except yaml.YAMLError as exc:
        raise ValueError(
            f"YAML inválido antes da alteração: {exc}"
        ) from exc

    validar(dicionario)

    backup = _backup(caminho)

    try:
        resultado = aplicar(dicionario)
        salvar_atomicamente(caminho, dicionario)

        # Reabre o arquivo final para garantir que a gravação realmente
        # produziu um YAML válido e estruturalmente consistente.
        validado = yaml.safe_load(
            caminho.read_text(encoding="utf-8")
        )

        validar(validado)

    except Exception:
        # O original já possui backup antes de qualquer escrita.
        raise

    print("OK: dicionário atualizado com sucesso.")
    print(f"Arquivo: {caminho}")
    print(f"Backup: {backup}")
    print(f"Intenções: {len(validado['intencoes'])}")
    print(f"Padrões adicionados: {resultado['padroes_adicionados']}")
    print(
        f"Intenções adicionadas: "
        f"{resultado['intencoes_adicionadas']}"
    )
    print(
        f"Precedências adicionadas: "
        f"{resultado['precedencias_adicionadas']}"
    )
    print(
        f"Exceções adicionadas: "
        f"{resultado['excecoes_adicionadas']}"
    )
    print("Validação final: OK")


if __name__ == "__main__":
    main()