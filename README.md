# AIZEN CHAMADOS

Automação operacional do processo de monitoramento de chamados do Salesforce para atualização do Plano N2.

## Objetivo

Ler o relatório `monitoramento.xlsx`, aplicar os tratamentos definidos pelo processo N2 e gerar uma cópia atualizada do arquivo `plano_n2_template.xlsx` em:

```text
data/output/plano_n2_gerado.xlsx
```

O projeto não utiliza:

- IA generativa no fluxo de decisão
- APIs externas
- integração direta com Salesforce
- banco de dados
- microsserviços

Toda a lógica ativa é baseada em regras operacionais determinísticas, catálogo canônico de causas, taxonomia validada pelo N2 e processamento local de planilhas Excel.

## Status do Projeto

**MVP 1 em validação final**

### Processo operacional

- ✅ Leitura do relatório Salesforce
- ✅ Atualização automática do Plano N2
- ✅ Idempotência por `Número do Chamado`
- ✅ Preservação das abas, tabelas, fórmulas e dashboards do template
- ✅ Inclusão automática apenas de chamados novos
- ✅ Atualização de sugestões em chamados já existentes
- ✅ Extração da descrição operacional
- ✅ Uso do assunto interno como contexto complementar
- ✅ Suggestion Engine determinístico
- ✅ Causa raiz padrão canônica
- ✅ Objeto Operacional Sugerido
- ✅ Classificação Sugerida
- ✅ Ambiguidade explícita
- ✅ Casos sem evidência retornam `NO_PATTERN`
- ✅ Classificação sem score probabilístico

### Conhecimento operacional

- ✅ Seis classificações oficiais
- ✅ Catálogo canônico de causas
- ✅ Aliases para padronização de causas históricas
- ✅ Todas as intenções ligadas por `causa_id`
- ✅ Taxonomia operacional consolidada
- ✅ Contrato de classificação documentado
- ✅ Hipótese H1 validada com a equipe N2
- ✅ Mapeamento `Classificação → Objeto Operacional`

### Estado atual do dicionário

```text
Intenções:          28
Causas canônicas:   30
Aliases de causas:  57
Assinaturas:        11
Classes oficiais:    6
Problemas:            0
```

### Métricas atuais

#### Histórico consolidado na planilha, antes da revisão de 2026-10-09

```text
Total:                  411
Classificados:          344
Cobertura automática: 83,7%
Ambíguos:                 7
Sem correspondência:     60
Por assinatura:         147
Por padrão:             197
```

#### Lote atual do `main.py`

```text
Total:                  157
Classificados:          130
Cobertura automática: 82,8%
Ambíguos:                 2
Sem correspondência:     25
Por assinatura:          56
Por padrão:              74
```

As métricas históricas são usadas para regressão e auditoria. A concordância operacional do N2 continua sendo o indicador principal.

O lote foi recalculado em 2026-10-09 sem atualizar a planilha operacional.
Cobertura mede quantos chamados receberam sugestão; não mede acerto.

## Princípio Central

A classificação representa o tipo de trabalho operacional executado pelo N2 e não necessariamente a forma como o cliente descreveu o problema.

A causa raiz e a classificação são conceitos diferentes:

```text
Descrição operacional
        ↓
Intenção identificada
        ↓
Causa raiz padrão
        ↓
Classificação oficial
```

Exemplo:

```text
Descrição: "Preciso alterar o vencimento do boleto"
Causa raiz: Alteração de vencimento
Classificação: Pagamentos, Boletos e Recebimentos
```

## As Seis Classificações Oficiais

1. Cancelamento e Reemissão de Nota Fiscal
2. Cobrança e Contestação
3. Pagamentos, Boletos e Recebimentos
4. Contratos, Comercial e Cadastro
5. Atendimento Administrativo e Suporte
6. Faturamento e Obrigações Fiscais

Nenhuma regra ativa pode produzir uma classificação fora dessa lista.

## Catálogo Canônico de Causas

O dicionário centraliza as causas na seção `causas`:

```yaml
causas:
  CONTESTACAO_COBRANCA:
    nome: Contestação de cobrança
    classificacao: Cobrança e Contestação
```

As intenções referenciam uma causa por ID:

```yaml
- id: INT_COB_CONTESTACAO
  intencao: Contestar divergência, valor ou critério de cobrança.
  causa_id: CONTESTACAO_COBRANCA
```

Esse modelo evita repetir nomes e classificações em regras diferentes.

### Padronização de causas históricas

A seção `aliases_causas` converte nomes históricos equivalentes para uma causa única:

```yaml
aliases_causas:
  Ajuste de cobrança / faturamento: CONTESTACAO_COBRANCA
  Dúvidas sobre cobrança: CONTESTACAO_COBRANCA
  Dúvida cobrança: CONTESTACAO_COBRANCA
```

A correspondência de aliases é exata. Causas como `Outros` ou descrições com múltiplas solicitações não são forçadas para uma causa canônica.

## Fluxo Operacional

```text
monitoramento.xlsx
        |
        v
leitura e normalização
        |
        +--> CNPJ
        |       |
        |       +--> Referências
        |               |
        |               +--> Razão Social
        |
        +--> Descrição bruta
        |       |
        |       +--> Assunto interno
        |       +--> Descrição do problema
        |       +--> Descrição detalhada enxuta
        |       +--> Entrada de classificação
        |
        +--> Status
        |       |
        |       +--> Situação
        |
        +--> Data de abertura
        |       |
        |       +--> Dias em Aberto
        |
        +--> Suggestion Engine
                |
                +--> Conceitos canônicos
                +--> Intenção identificada
                +--> causa_id
                +--> Causa raiz padrão
                +--> Classificação oficial
                +--> Objeto Operacional Sugerido
                +--> Motivo da decisão
                +--> Ambiguidade ou NO_PATTERN
        |
        v
plano_n2_gerado.xlsx
```

## Entrada de Classificação

A coluna `Descrição detalhada` permanece enxuta para uso operacional.

Para classificar, o motor combina:

```text
Assunto interno + Descrição detalhada
```

O assunto interno complementa a descrição, mas não substitui a necessidade de evidência operacional.

## Fluxo de Decisão do Motor

```text
Texto
  ↓
Normalização
  ↓
Extração de ação, objeto, contexto e canal
  ↓
Assinaturas canônicas
  ↓
Padrões textuais como fallback
  ↓
Causa canônica
  ↓
Classificação oficial
```

### Estados possíveis

- `CLASSIFIED_SIGNATURE`: decisão por assinatura canônica
- `CLASSIFIED_PATTERN`: decisão pelo fallback textual
- `AMBIGUOUS_CAUSE`: duas ou mais intenções igualmente válidas
- `NO_PATTERN`: evidência insuficiente
- `EMPTY_TEXT`: texto vazio após normalização

O motor não escolhe arbitrariamente quando existem duas ações operacionais válidas.

Exemplo:

```text
"Anular a NF e dar baixa no boleto"
```

Resultado:

```text
Ambígua
Candidatas:
- Cancelamento de NF
- Cancelamento de boleto
```

## Objetos Operacionais

- Documento Fiscal
- Título Financeiro
- Valor Cobrado
- Contrato/Cadastro
- Informação/Atendimento
- Parâmetro de Faturamento

## Arquitetura

O fluxo é intencionalmente simples e mantido por poucos módulos.

### Núcleo

- `src/extract.py`: leitura das planilhas
- `src/parse_description.py`: extração do formulário, descrição operacional e CNPJ
- `src/lookup.py`: busca da razão social
- `src/business_rules.py`: cálculo de situação e dias em aberto
- `src/root_cause_engine.py`: catálogo, assinaturas, padrões, causa e classificação
- `src/text_rules.py`: normalização, negação explícita e associação entre ação e objeto
- `src/classification_input.py`: entrada compartilhada pelo fluxo principal, backfill e avaliações
- `src/schema.py`: colunas de sugestão, validação e atualização automática
- `src/export.py`: atualização do template Excel
- `src/main.py`: orquestração do processo

### Backfill e métricas

- `src/backfill_suggestions.py`: reprocessamento dos chamados históricos
- `src/aizen_metrics.py`: cobertura, distribuição, divergências e exportações

### Análise

- `src/decision_analysis.py`: análise histórica
- `src/dictionary_analysis.py`: auditoria do dicionário
- `src/root_cause_analysis.py`: análise exploratória de causas
- `src/uncovered_analysis.py`: análise de casos sem correspondência
- `src/validation_analysis.py`: concordância operacional

## Estrutura de Pastas

```text
aizen_chamados/
├── data/
│   ├── input/
│   │   ├── causa_raiz_rules.yaml
│   │   ├── causa_raiz_taxonomia.yaml
│   │   ├── dicionario_aizen_intencoes.yaml
│   │   ├── monitoramento.xlsx
│   │   └── plano_n2_template.xlsx
│   │
│   └── output/
│       ├── plano_n2_gerado.xlsx
│       ├── aizen_sem_padrao.xlsx
│       ├── aizen_divergencias.xlsx
│       ├── aizen_ambiguos.xlsx
│       ├── decisao_analise.json
│       ├── causa_raiz_analise.json
│       ├── validation_analysis.json
│       ├── uncovered_analysis.json
│       └── dicionario_aizen_analise.json
│
├── src/
│   ├── aizen_metrics.py
│   ├── backfill_suggestions.py
│   ├── business_rules.py
│   ├── decision_analysis.py
│   ├── dictionary_analysis.py
│   ├── export.py
│   ├── extract.py
│   ├── lookup.py
│   ├── main.py
│   ├── parse_description.py
│   ├── root_cause_analysis.py
│   ├── root_cause_engine.py
│   ├── uncovered_analysis.py
│   └── validation_analysis.py
│
├── tests/
│   ├── test_dictionary_analysis.py
│   ├── test_main_classification.py
│   ├── test_root_cause_engine.py
│   ├── test_uncovered_analysis.py
│   ├── test_validation_analysis.py
│   └── test_validation_workflow.py
│
├── classification_contract.md
├── README.md
└── requirements.txt
```

## Idempotência

A chave de idempotência é:

```text
Número do Chamado
```

Chamados já existentes no compilado não são inseridos novamente. As sugestões podem ser atualizadas em registros existentes quando o motor ou o dicionário evoluem.

## Documentos de Referência

### `classification_contract.md`

Define:

- as seis classificações oficiais
- os objetos operacionais correspondentes
- a hipótese H1
- o indicador principal do projeto

### `data/input/dicionario_aizen_intencoes.yaml`

Fonte ativa do motor. Contém:

- classes permitidas
- catálogo canônico de causas
- aliases de causas históricas
- vocabulário de ações, objetos, contextos e canais
- intenções
- assinaturas
- padrões
- exclusões

### `data/input/causa_raiz_taxonomia.yaml`

Mantém a taxonomia operacional e a compatibilidade com análises históricas.

### `data/input/causa_raiz_rules.yaml`

Referência histórica de regras exploratórias. Não controla a classificação ativa.

## Como Executar

Execute os comandos a partir da raiz do projeto.

### Instalar dependências

Windows:

```powershell
py -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m pip install -r requirements.txt
```

### Validar o dicionário e o motor

Windows:

```powershell
py src/root_cause_engine.py
```

Linux/macOS:

```bash
python3 src/root_cause_engine.py
```

Saída esperada:

```text
Intenções no dicionário: 28
Causas canônicas: 30
Aliases de causas: 57
Problemas no dicionário: 0
```

### Gerar o Plano N2

Windows:

```powershell
py src/main.py
```

Linux/macOS:

```bash
python3 src/main.py
```

Saída:

```text
data/output/plano_n2_gerado.xlsx
```

### Executar o backfill histórico

Windows:

```powershell
py src/backfill_suggestions.py
```

Linux/macOS:

```bash
python3 src/backfill_suggestions.py
```

### Gerar métricas e relatórios operacionais

Windows:

```powershell
py src/aizen_metrics.py
```

Linux/macOS:

```bash
python3 src/aizen_metrics.py
```

Arquivos gerados:

```text
data/output/aizen_sem_padrao.xlsx
data/output/aizen_divergencias.xlsx
data/output/aizen_ambiguos.xlsx
```

### Executar testes automatizados

Windows:

```powershell
py -m pytest
```

Linux/macOS:

```bash
python3 -m pytest
```

Os testes verificam:

- integridade do catálogo
- causa_id válido
- classes oficiais
- assinaturas
- precedência entre intenção genérica e específica
- casos ambíguos
- casos sem correspondência
- regressões do fluxo principal

A regressão do lote de 157 chamados está em `tests/test_regressao_lote157.py`
e participa da execução padrão. A revisão de 2026-10-09 passou em 157 testes,
incluindo negativas, limites de frases, pedidos mistos, tempo de revisão do N2
e saneamento das fórmulas herdadas do Excel. O exportador preserva valores manuais,
sinaliza causas sem referência e trata descrições vazias. Os indicadores herdados
do Panorama contam diretamente os status no mesmo recorte histórico da tabela
dinâmica, sem depender de seu cache inválido.

## Análises Disponíveis

### Relatório de taxonomia e classificação

```powershell
py src/decision_analysis.py
```

Gera:

```text
data/output/decisao_analise.json
```

### Análise exploratória de causas raiz

```powershell
py src/root_cause_analysis.py
```

Gera:

```text
data/output/causa_raiz_analise.json
```

### Auditoria do dicionário

```powershell
py src/dictionary_analysis.py
```

Gera:

```text
data/output/dicionario_aizen_analise.json
```

### Análise de validação operacional

Após o N2 preencher `Objeto Operacional Validado` e `Classificação Validada`:

```powershell
py src/validation_analysis.py
```

Gera:

```text
data/output/validation_analysis.json
```

### Análise de casos sem sugestão

```powershell
py src/uncovered_analysis.py
```

Gera:

```text
data/output/uncovered_analysis.json
```

Os agrupamentos são exploratórios. O N2 decide quais padrões justificam novas regras.

## Colunas de Sugestão

O processo exporta:

- Intenção Identificada
- Causa Identificada
- ID Causa Padrão
- Causa Raiz Padrão
- Objeto Operacional Sugerido
- Classificação Sugerida
- Score Confiança
- Regra Sugerida
- Status da Sugestão
- Motivo da Decisão
- Ambiguidade

`Score Confiança` é uma coluna legada. O valor permanece vazio e não participa da decisão.

Nos chamados existentes, a exportação atualiza sugestões e os campos automáticos
definidos em `src/schema.py`, incluindo status, situação, dias em aberto,
descrições e dados de referência. Campos manuais e validações do N2 são
preservados. No backfill, campos operacionais ausentes não são sobrescritos.

## Campos que Continuam Manuais

- RESPONSÁVEL
- Prioridade
- Ofensor
- Observação/Ação
- Objeto Operacional Validado
- Classificação Validada

A validação manual é usada para medir concordância e revisar casos ambíguos, sem correspondência ou discordantes.

## Indicador Principal

O KPI principal é a **Concordância de Classificação**:

```text
Sugestões validadas pelo N2 que correspondem à classificação sugerida
```

O acerto histórico é uma métrica de regressão e auditoria, mas não substitui a validação operacional.

## Critérios para Evoluir o Dicionário

Uma nova causa deve:

1. representar uma ação operacional distinta
2. exigir tratamento diferente da equipe
3. ser reutilizável em chamados futuros
4. não caber em uma causa existente
5. possuir uma classificação oficial clara

Uma nova regra não deve ser criada a partir de um único chamado específico.

Prefira:

```text
ação + objeto
ação + objeto + contexto
objeto + contexto inequívoco
```

Evite:

```text
termos isolados
nomes de clientes
CNPJ
número de chamado
frase completa de um único caso
```

## O Que Já Funciona

- Leitura do relatório Salesforce
- Leitura da aba Referências
- Extração e normalização do CNPJ
- Extração do assunto interno
- Extração e normalização da descrição
- Lookup de Razão Social
- Construção do layout Compilado chamados
- Cálculo de Situação
- Cálculo de Dias em Aberto
- Preservação do template, fórmulas e dashboards
- Inclusão idempotente de chamados
- Atualização de sugestões existentes
- Catálogo canônico de causas
- Aliases de causas históricas
- Assinaturas determinísticas
- Fallback por padrões
- Causa raiz padrão
- Classificação oficial
- Objeto Operacional Sugerido
- Ambiguidade explícita
- Exportação para Excel
- Relatórios de cobertura e divergência
- Persistência das validações do N2

## Próximos Passos

1. revisar as divergências reais antes de expandir cobertura
2. corrigir vocabulários duplicados ou conceitos cadastrados no grupo errado
3. transformar os testes críticos em testes permanentes
4. remover o campo legado `causa_canonica` após confirmar que nenhum módulo depende dele
5. revisar os 60 casos históricos sem correspondência
6. acumular validações operacionais do N2
7. congelar e versionar o MVP 1

## Piloto e fechamento do MVP

O fluxo de revisão, os critérios propostos ao N2 e o congelamento reproduzível
estão em [docs/validacao_mvp.md](docs/validacao_mvp.md). `src/mvp_pilot.py` prepara
e mede o piloto; `src/mvp_release.py` preserva a candidata com hashes e ZIP.
Chamados já utilizados na calibração não contam para o aceite prospectivo.
Os limites em `data/input/criterios_mvp.yaml` aguardam confirmação do N2.

## Resultado Esperado

Quando um novo chamado chega:

```text
Descrição bruta
        ↓
Descrição operacional
        ↓
Intenção identificada
        ↓
Causa raiz padrão
        ↓
Classificação oficial
```

O objetivo é reduzir o esforço de triagem, manter consistência operacional e preservar a revisão humana nos casos em que não existe evidência segura.
