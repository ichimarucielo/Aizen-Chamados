# AIZEN CHAMADOS

Automação operacional do processo de monitoramento de chamados Salesforce para atualização do Plano N2.

## Objetivo

Ler o relatório `monitoramento.xlsx`, aplicar os tratamentos já definidos no processo N2 e gerar uma cópia atualizada de `plano_n2_template.xlsx` em `data/output/plano_n2_gerado.xlsx`.

O projeto não usa IA generativa, API Salesforce, banco de dados ou microsserviços.

## Documentos de referência

Explicam como o N2 pensa e devem ser lidos antes de mexer em regras:

- `classification_contract.md`: o objeto operacional de cada classificação, a hipótese H1 e o indicador principal (acerto de classificação).
- `data/input/causa_raiz_taxonomia.yaml`: variante histórica de causa raiz, grupo e classificação. É um rascunho para revisão do N2.
- `src/decision_analysis.py`: decisão mais frequente por causa raiz, com confiança, e o relatório de quais causas cada classificação absorve.

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
│   │   ├── causa_raiz_rules.yaml
│   │   ├── causa_raiz_taxonomia.yaml
│   │   ├── monitoramento.xlsx
│   │   └── plano_n2_template.xlsx
│   └── output/
├── src/
│   ├── business_rules.py
│   ├── decision_analysis.py
│   ├── export.py
│   ├── extract.py
│   ├── lookup.py
│   ├── main.py
│   ├── parse_description.py
│   ├── root_cause_analysis.py
│   └── root_cause_engine.py
├── classification_contract.md
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

Para medir a decisão histórica por causa raiz e o relatório classificação → causas:

```powershell
$env:PYTHONPATH = "src"
python src/decision_analysis.py
```

Para avaliar o acerto de classificação das regras contra o histórico (use
`--incluir-rascunho` para incluir regras ainda não aprovadas):

```powershell
$env:PYTHONPATH = "src"
python src/root_cause_engine.py --incluir-rascunho
```

Esses dois scripts são de análise e não estão ligados ao `main.py`.

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
4. Revisar com o N2 o `classification_contract.md`, a taxonomia e as regras em rascunho. Só regras aprovadas entram no pipeline.
5. Testar a hipótese H1 em chamados novos, medindo o acerto de classificação.
