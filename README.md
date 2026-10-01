# AIZEN CHAMADOS

Automação operacional do processo de monitoramento de chamados Salesforce para atualização do Plano N2.

## Objetivo

Ler o relatório `monitoramento.xlsx`, aplicar os tratamentos já definidos no processo N2 e gerar uma cópia atualizada de `plano_n2_template.xlsx` em `data/output/plano_n2_gerado.xlsx`.

O projeto não usa IA generativa, API Salesforce, banco de dados ou microsserviços.

## Fluxo operacional

```text
monitoramento.xlsx
        |
        v
leitura e normalização em Python
        |
        +--> CNPJ -> Referencias -> Razão social
        +--> descrição -> Descrição detalhada
        +--> status -> Situação
        +--> data de abertura -> Dias em Aberto
        |
        v
plano_n2_gerado.xlsx
```

## Arquitetura

O fluxo é intencionalmente simples:

- `src/extract.py`: leitura das planilhas de entrada e das abas do template.
- `src/parse_description.py`: normalização da descrição e extração do CNPJ.
- `src/lookup.py`: busca da razão social nas referências.
- `src/business_rules.py`: regras de situação e dias em aberto.
- `src/export.py`: cópia do template e inclusão idempotente na aba `Compilado chamados`.
- `src/main.py`: orquestração e construção do DataFrame final.

A chave de idempotência é `Número do Chamado`. Chamados já existentes no template não são duplicados.

## Estrutura de pastas

```text
aizen_chamados/
├── data/
│   ├── input/
│   │   ├── monitoramento.xlsx
│   │   └── plano_n2_template.xlsx
│   └── output/
├── src/
│   ├── business_rules.py
│   ├── export.py
│   ├── extract.py
│   ├── lookup.py
│   ├── main.py
│   ├── parse_description.py
│   └── root_cause_analysis.py
└── README.md
```

## Como executar

Na raiz do projeto, com Python e as dependências `pandas`, `openpyxl` e `xlrd` disponíveis:

```powershell
$env:PYTHONPATH = "src"
python src/main.py
```

O arquivo será salvo em:

```text
data/output/plano_n2_gerado.xlsx
```

Para analisar os históricos e gerar candidatos de termos para o dicionário de
causa raiz:

```powershell
$env:PYTHONPATH = "src"
python src/root_cause_analysis.py
```

O resultado exploratório é salvo em
`data/output/causa_raiz_analise.json`. Os termos são candidatos para revisão
da equipe N2; o script não classifica chamados automaticamente.

O dicionário operacional em estado de rascunho está em
`data/input/causa_raiz_rules.yaml`. Ele só deve ser usado no pipeline depois
da validação dos termos pela equipe N2.

## O que já funciona

- Leitura do relatório Salesforce.
- Leitura da aba `Referencias `.
- Extração e normalização do CNPJ e da descrição.
- Lookup de razão social.
- Construção das 28 colunas da aba `Compilado chamados`.
- Cálculo de `Situação` e `Dias em Aberto`.
- Preservação das abas e fórmulas existentes do template.
- Herança de estilos e fórmulas relativas da última linha válida para novos chamados.
- Inclusão somente de chamados novos.

## O que ainda depende do processo manual

- `Causa raiz`, `Classificação`, `RESPONSÁVEL`, `Prioridade`, `Ofensor` e outros campos operacionais não são inventados pelo programa quando não existem no relatório de origem.
- A classificação só pode ser derivada quando houver uma causa raiz preenchida e correspondente nas referências.
- Não há integração automática com Salesforce.

## Próximos passos

1. Validar com a equipe N2 quais campos manuais devem continuar sendo preenchidos depois da exportação.
2. Definir a origem oficial de `Causa raiz` e `Classificação` quando esses campos vierem vazios no Salesforce.
3. Adicionar testes automatizados para novos layouts de relatório e para a idempotência do arquivo final.
4. Revisar os candidatos gerados por `root_cause_analysis.py` e transformar somente as regras aprovadas pela equipe N2 em lógica operacional.
