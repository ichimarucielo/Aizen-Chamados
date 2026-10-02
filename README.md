AIZEN CHAMADOS

Automação operacional do processo de monitoramento de chamados Salesforce para atualização do Plano N2.

Objetivo

Ler o relatório monitoramento.xlsx, aplicar os tratamentos definidos pelo processo N2 e gerar uma cópia atualizada de plano_n2_template.xlsx em:

data/output/plano_n2_gerado.xlsx


O projeto não utiliza:

IA generativa
APIs externas
Integração Salesforce
Banco de dados
Microsserviços

Toda a lógica é baseada em regras operacionais, taxonomia validada pelo N2 e processamento local de planilhas Excel.

Status do Projeto
Produção

✅ Leitura do relatório Salesforce

✅ Atualização automática do Plano N2

✅ Idempotência por Número do Chamado

✅ Preservação das abas, tabelas, fórmulas e dashboards do template

✅ Inclusão automática apenas de chamados novos

✅ Suggestion Engine operacional

✅ Objeto Operacional Sugerido

✅ Classificação Sugerida

✅ Score de Confiança

Conhecimento Operacional

✅ Taxonomia operacional consolidada

✅ Contrato de classificação documentado

✅ Hipótese H1 validada com a equipe N2

✅ Mapeamento Classificação → Objeto Operacional

Evolução

🔄 Aumentar cobertura das sugestões

🔄 Refinar regras aprovadas pelo N2

🔄 Medir taxa de concordância operacional

Documentos de Referência

Esses documentos representam o conhecimento operacional descoberto durante o projeto e devem ser lidos antes de alterar regras ou taxonomia.

classification_contract.md

Define:

As 6 classificações oficiais
Os objetos operacionais correspondentes
A hipótese H1
O indicador principal do projeto

Princípio central:

A classificação representa o tipo de trabalho operacional executado pelo N2 e não necessariamente o problema relatado pelo cliente.

data/input/causa_raiz_taxonomia.yaml

Taxonomia operacional contendo:

Causa histórica
        ↓
Grupo canônico
        ↓
Classificação


Mantém compatibilidade com o histórico analisado.

data/input/causa_raiz_rules.yaml

Regras operacionais utilizadas pelo motor de sugestão.

Possui status:

aprovado
revisar
descartar


Apenas regras aprovadas devem ser utilizadas em produção.

src/decision_analysis.py

Ferramenta analítica utilizada para:

Medir frequência histórica
Identificar decisão predominante
Avaliar confiança
Gerar relatório Classificação → Causas → Quantidade
Fluxo Operacional
monitoramento.xlsx
        |
        v
leitura e normalização
        |
        +--> CNPJ
        |       |
        |       +--> Referencias
        |               |
        |               +--> Razão Social
        |
        +--> Descrição
        |       |
        |       +--> Descrição detalhada
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
        |       |
        |       +--> Objeto Operacional Sugerido
        |       +--> Classificação Sugerida
        |       +--> Score de Confiança
        |
        v
plano_n2_gerado.xlsx

Arquitetura

O fluxo é intencionalmente simples.

Núcleo
src/extract.py → leitura das planilhas.
src/parse_description.py → normalização da descrição e extração de informações.
src/lookup.py → busca da razão social.
src/business_rules.py → cálculo de situação e dias em aberto.
src/root_cause_engine.py → motor de sugestão operacional.
src/export.py → exportação para o template.
src/main.py → orquestração do processo.
Análise
src/decision_analysis.py → análise histórica e confiança.
classification_contract.md → contrato operacional.
data/input/causa_raiz_taxonomia.yaml → taxonomia.
data/input/causa_raiz_rules.yaml → regras do motor.

A chave de idempotência é:

Número do Chamado


Chamados já existentes no compilado não são inseridos novamente.

Hipótese H1

A hipótese operacional validada durante a análise histórica é:

É mais fácil identificar o objeto operacional que será tratado pelo N2 do que identificar a causa raiz exata.

Fluxo conceitual:

Descrição
        ↓
Objeto Operacional
        ↓
Classificação


Objetos operacionais:

Documento Fiscal

Título Financeiro

Valor Cobrado

Contrato/Cadastro

Informação/Atendimento

Parâmetro de Faturamento

Estrutura de Pastas
aizen_chamados/
├── data/
│   ├── input/
│   │   ├── causa_raiz_rules.yaml
│   │   ├── causa_raiz_taxonomia.yaml
│   │   ├── monitoramento.xlsx
│   │   └── plano_n2_template.xlsx
│   │
│   └── output/
│       └── plano_n2_gerado.xlsx
│
├── src/
│   ├── business_rules.py
│   ├── decision_analysis.py
│   ├── export.py
│   ├── extract.py
│   ├── lookup.py
│   ├── main.py
│   ├── parse_description.py
│   └── root_cause_engine.py
│
├── classification_contract.md
└── README.md

Como Executar

Na raiz do projeto:

$env:PYTHONPATH = "src"
python src/main.py


Saída:

data/output/plano_n2_gerado.xlsx

Análises Disponíveis
Relatório de Taxonomia e Classificação
$env:PYTHONPATH = "src"
python src/decision_analysis.py


Gera análises de:

confiança histórica
distribuição de causas
classificação → causas
cobertura
Avaliação do Motor

Utilizando apenas regras aprovadas:

$env:PYTHONPATH = "src"
python src/root_cause_engine.py


Incluindo regras em revisão:

$env:PYTHONPATH = "src"
python src/root_cause_engine.py --incluir-rascunho


Métricas:

Cobertura

Acerto de Classificação

Ambiguidade

Desempenho por classificação


Esses scripts são de análise e não alteram o Plano N2.

O Que Já Funciona
Leitura do relatório Salesforce.
Leitura da aba Referencias.
Extração e normalização do CNPJ.
Extração e normalização da descrição.
Lookup de Razão Social.
Construção do layout Compilado chamados.
Cálculo de Situação.
Cálculo de Dias em Aberto.
Preservação das abas do template.
Preservação dos dashboards.
Preservação das fórmulas existentes.
Herança automática de estilos e fórmulas.
Inclusão idempotente de chamados.
Suggestion Engine.
Objeto Operacional Sugerido.
Classificação Sugerida.
Score de Confiança.
Exportação automática das sugestões para Excel.
O Que Continua Manual

Os seguintes campos continuam dependentes da operação N2:

Causa raiz
RESPONSÁVEL
Prioridade
Ofensor
Observação/Ação

As sugestões geradas pelo sistema:

Objeto Operacional Sugerido

Classificação Sugerida

Score de Confiança


são apenas apoio operacional e não substituem validação humana.

Indicador Principal

O indicador principal do projeto é:

Acerto de Classificação


e não:

Acerto da Causa Raiz


Isso reflete o modelo operacional adotado pelo N2.

Próximos Passos
Medir cobertura da Suggestion Engine em chamados novos.
Medir taxa de concordância do N2 com as sugestões geradas.
Aumentar cobertura sem reduzir precisão.
Revisar periodicamente taxonomia e regras operacionais.
Adicionar testes automatizados para o motor de sugestão.
Consolidar métricas de validação operacional.
Evoluir a taxonomia apenas após validação do N2.
Resultado Esperado

Quando um novo chamado chega:

Descrição
        ↓
Objeto Operacional Sugerido
        ↓
Classificação Sugerida
        ↓
Confiança


permitindo ao N2 reduzir esforço de triagem e manter consistência operacional.