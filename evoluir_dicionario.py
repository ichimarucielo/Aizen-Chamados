
"""Evolui o dicionário AIZEN: adiciona padrões, precedências e exceções comprovados.

Uso:
    python evoluir_dicionario.py [caminho_do_yaml]

- Só acrescenta; não remove nem reatribui nada do que já existe.
- Idempotente.
- Se um padrão (comparado após a normalização do motor) ficar em mais de uma intenção,
  ABORTA e lista os conflitos. Nada é gravado.
- Valida IDs de precedência, classes permitidas e causa padrão -> classe.
- Faz backup com timestamp antes de salvar.
- Não cria intenção nova: isso vem da análise do histórico, não deste script.
"""

import difflib
import sys
from datetime import datetime
from pathlib import Path
from shutil import copy2

import yaml

sys.path.insert(0, "src")  # roda da raiz do projeto

from root_cause_engine import normalize_text


DEFAULT = Path(
    "data/input/dicionario_aizen_intencoes.yaml"
)


# ---------------------------------------------------------------------------
# PADRÕES NOVOS
# ---------------------------------------------------------------------------

PADROES = {
    "INT_NF_CANCEL_REEMISSAO": [
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
        "corrigir descritivo dos serviços",
    ],

    "INT_FAT_REENVIO_NF": [
        "encaminhar as nfs",
        "encaminhar notas fiscais",
    ],

    "INT_CON_CANCELAMENTO": [
        "solicito o cancelamento do mesmo + contrato",
        "cancelamento do serviço",
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

    "INT_NF_REEMISSAO_PO": [
        "cancelar substituir nf com po",
        "cancelar e substituir nf com po",
        "substituir nf com po",
        "cancelar/substituir nf com po",
    ],

    "INT_CON_CONGELAMENTO": [
        "congelar o contrato",
    ],
}


# ---------------------------------------------------------------------------
# PRECEDÊNCIAS
# ---------------------------------------------------------------------------

PRECEDENCIA = [
    {
        "preferir": "INT_PAG_VENCIMENTO",
        "sobre": [
            "INT_PAG_BOLETO_REENVIO",
            "INT_PAG_FINANCEIRO",
        ],
        "quando": "O pedido é mudar a data/prazo; reenviar boleto é só o meio.",
    },
    {
        "preferir": "INT_NF_CANCEL_REEMISSAO",
        "sobre": [
            "INT_FAT_REENVIO_NF",
        ],
        "quando": "Pede cancelar e emitir nova NF, não apenas reenviar.",
    },
    {
        "preferir": "INT_NF_REEMISSAO_PO",
        "sobre": [
            "INT_NF_CANCEL_REEMISSAO",
        ],
        "quando": (
            "Quando a substituição da NF envolve PO, "
            "a intenção específica de NF com PO prevalece "
            "sobre o cancelamento/reemissão genérico."
        ),
    },
]


# ---------------------------------------------------------------------------
# EXCEÇÕES
# ---------------------------------------------------------------------------

EXCECOES = [
    {
        "id": "valor_nf_contestar_vs_verificar",
        "causa_ou_rotulo": (
            "Dúvida/divergência de valor da NF ou transações"
        ),
        "regra": (
            "Histórico: contestar/questionar valor, volume "
            "ou transações cobradas => Cobrança e Contestação; "
            "confirmar qual NF é válida, duas NFs recebidas, "
            "valor correto para pagar ou MIDs cobrados => "
            "Faturamento e Obrigações Fiscais."
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
            "Dicionário adota Faturamento: a ação é verificar "
            "o faturamento."
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
            "A classe decorre da ação pedida no corpo do chamado; "
            "nesses chamados o rótulo histórico não é usado "
            "como evidência."
        ),
    },
]


# ---------------------------------------------------------------------------
# UTILITÁRIOS
# ---------------------------------------------------------------------------

def _chave(padrao: str) -> str:
    """Chave de comparação igual à normalização usada pelo motor."""

    partes = []

    for parte in padrao.split("+"):
        normalizado = normalize_text(parte)

        if normalizado:
            partes.append(normalizado)

    return " + ".join(sorted(partes))


# ---------------------------------------------------------------------------
# APLICAÇÃO
# ---------------------------------------------------------------------------

def aplicar(d: dict) -> dict:
    por_id = {
        intencao["id"]: intencao
        for intencao in d["intencoes"]
    }

    # ---------------------------------------------------------------
    # Padrões
    # ---------------------------------------------------------------
    for intencao_id, novos in PADROES.items():
        if intencao_id not in por_id:
            raise ValueError(
                f"Intenção inexistente: {intencao_id}"
            )

        atuais = por_id[intencao_id].setdefault(
            "padroes",
            [],
        )

        existentes = {
            _chave(padrao)
            for padrao in atuais
        }

        for padrao in novos:
            chave = _chave(padrao)

            if not chave:
                continue

            if chave not in existentes:
                atuais.append(padrao)
                existentes.add(chave)

    # ---------------------------------------------------------------
    # Precedências
    # ---------------------------------------------------------------
    precedencias = d.setdefault(
        "precedencia",
        [],
    )

    for regra in PRECEDENCIA:
        existe = any(
            atual.get("preferir")
            == regra["preferir"]
            and atual.get("sobre", [])
            == regra["sobre"]
            for atual in precedencias
        )

        if not existe:
            precedencias.append(regra)

    # ---------------------------------------------------------------
    # Exceções
    # ---------------------------------------------------------------
    excecoes = d.setdefault(
        "conflitos_e_excecoes",
        [],
    )

    ids_existentes = {
        excecao["id"]
        for excecao in excecoes
    }

    excecoes.extend(
        excecao
        for excecao in EXCECOES
        if excecao["id"]
        not in ids_existentes
    )

    # ---------------------------------------------------------------
    # Validação das precedências
    # ---------------------------------------------------------------
    erros = []

    for regra in precedencias:
        alvos = [
            regra["preferir"],
            *regra.get("sobre", []),
        ]

        for alvo in alvos:
            if alvo in por_id:
                continue

            sugestao = difflib.get_close_matches(
                alvo,
                por_id,
                n=1,
            )

            mensagem = (
                f"  {alvo!r} "
                f"(regra preferir={regra['preferir']!r})"
            )

            if sugestao:
                mensagem += (
                    f" -> você quis dizer "
                    f"{sugestao[0]!r}?"
                )

            erros.append(mensagem)

    if erros:
        raise ValueError(
            "Precedência aponta para intenção inexistente:\n"
            + "\n".join(erros)
        )

    # ---------------------------------------------------------------
    # Validação de padrões duplicados entre intenções
    # ---------------------------------------------------------------
    donos = {}

    for intencao in d["intencoes"]:
        for padrao in intencao.get(
            "padroes",
            [],
        ):
            donos.setdefault(
                _chave(padrao),
                {},
            ).setdefault(
                intencao["id"],
                padrao,
            )

    duplicados = {
        chave: valores
        for chave, valores in donos.items()
        if len(valores) > 1
    }

    if duplicados:
        linhas = "\n".join(
            f"  {sorted(valores.values())}: "
            f"{sorted(valores)}"
            for valores in duplicados.values()
        )

        raise ValueError(
            "Padrão em mais de uma intenção "
            "(remova a cópia errada no YAML):\n"
            + linhas
        )

    # ---------------------------------------------------------------
    # Validação de classes e causas
    # ---------------------------------------------------------------
    permitidas = set(
        d.get(
            "classes_permitidas",
            [],
        )
    )

    causa_classe = {}

    for intencao in d["intencoes"]:
        classificacao = intencao[
            "classificacao"
        ]

        if (
            permitidas
            and classificacao
            not in permitidas
        ):
            raise ValueError(
                f"Classe fora do contrato: "
                f"{intencao['id']}"
            )

        causa = intencao[
            "causa_padrao"
        ]

        if causa not in causa_classe:
            causa_classe[
                causa
            ] = classificacao
            continue

        if (
            causa_classe[causa]
            != classificacao
        ):
            raise ValueError(
                f"Causa com duas classes: "
                f"{causa}"
            )

    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    caminho = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else DEFAULT
    )

    dicionario = yaml.safe_load(
        caminho.read_text(
            encoding="utf-8"
        )
    )

    dicionario = aplicar(
        dicionario
    )

    backup = caminho.with_name(
        f"{caminho.name}."
        f"{datetime.now():%Y%m%d_%H%M%S}.bak"
    )

    copy2(
        caminho,
        backup,
    )

    caminho.write_text(
        yaml.safe_dump(
            dicionario,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        ),
        encoding="utf-8",
    )

    print(
        f"OK: "
        f"{len(dicionario['intencoes'])} intenções, "
        f"{len(dicionario['precedencia'])} precedências "
        f"-> {caminho}"
    )

    print(
        f"Backup: {backup}"
    )

