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

✅ Classificação determinística sem score

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

data/input/dicionario_aizen_intencoes.yaml

Dicionário ativo: intenção → causa raiz padrão → uma das seis classificações oficiais. Regras e precedências são determinísticas; conflitos não resolvidos retornam ambiguidade.

data/input/causa_raiz_taxonomia.yaml

Taxonomia operacional contendo:

Causa histórica
        ↓
Grupo canônico
        ↓
Classificação


Mantém compatibilidade com o histórico analisado.

data/input/causa_raiz_rules.yaml

Taxonomia e regras exploratórias anteriores, preservadas como referência histórica. O motor atual consulta `dicionario_aizen_intencoes.yaml`.

Esses status pertencem ao formato legado e não controlam a classificação ativa.

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
        |       +--> Causa identificada
        |       +--> Causa raiz padrão
        |       +--> Classificação automática
        |       +--> Objeto Operacional Sugerido
        |       +--> Classificação Sugerida
        |
        v
plano_n2_gerado.xlsx

Arquitetura

O fluxo é intencionalmente simples.

Classificação automática

`Descrição detalhada` é normalizada e comparada aos padrões de intenção em `data/input/dicionario_aizen_intencoes.yaml`. Uma intenção determina sua causa raiz padrão e, por consequência, uma classificação oficial. Padrões da mesma intenção são consolidados; precedências explícitas resolvem contextos incidentais. Sem correspondência ou com conflito não resolvido, não há classificação automática.

Núcleo
src/extract.py → leitura das planilhas.
src/parse_description.py → normalização da descrição e extração de informações.
src/lookup.py → busca da razão social.
src/business_rules.py → cálculo de situação e dias em aberto.
src/root_cause_engine.py → identifica intenção, normaliza a causa padrão e deriva a classificação oficial.
src/export.py → exportação para o template.
src/main.py → orquestração do processo.
Análise
src/decision_analysis.py → análise histórica e confiança.
src/dictionary_analysis.py → auditoria do dicionário contra o histórico.
classification_contract.md → contrato operacional.
data/input/causa_raiz_taxonomia.yaml → taxonomia.
data/input/dicionario_aizen_intencoes.yaml → dicionário ativo do motor.

A chave de idempotência é:

Número do Chamado


Chamados já existentes no compilado não são inseridos novamente.

Hipótese H1

A hipótese operacional validada durante a análise histórica é:

É mais fácil identificar o objeto operacional que será tratado pelo N2 do que identificar a causa raiz exata.

Fluxo conceitual:

Descrição
        ↓
Identificação da causa
        ↓
Causa raiz padrão
        ↓
Classificação oficial


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
│   │   ├── dicionario_aizen_intencoes.yaml
│   │   ├── monitoramento.xlsx
│   │   └── plano_n2_template.xlsx
│   │
│   └── output/
│       ├── plano_n2_gerado.xlsx
│       ├── decisao_analise.json
│       ├── causa_raiz_analise.json
│       ├── validation_analysis.json
│       ├── uncovered_analysis.json
│       └── dicionario_aizen_analise.json
│
├── src/
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
├── requirements.txt
├── tests/
│   ├── test_dictionary_analysis.py
│   ├── test_root_cause_engine.py
│   ├── test_main_classification.py
│   ├── test_uncovered_analysis.py
│   ├── test_validation_analysis.py
│   └── test_validation_workflow.py
├── classification_contract.md
└── README.md

Como Executar

Com Python instalado, execute os comandos a partir da raiz do projeto. Instale as dependências uma vez:

Windows:

py -m pip install -r requirements.txt

Linux/macOS:

python3 -m pip install -r requirements.txt

Testes Automatizados

Execute a partir da raiz do projeto:

Windows: `py -m pytest`

Linux/macOS: `python3 -m pytest`

Os testes verificam intenções equivalentes, precedência, casos ambíguos, classes oficiais e análise histórica.

Para gerar o Plano N2:

Windows: `py src/main.py`

Linux/macOS: `python3 src/main.py`


Saída:

data/output/plano_n2_gerado.xlsx

Análises Disponíveis
Relatório de Taxonomia e Classificação
Windows: `py src/decision_analysis.py`

Linux/macOS: `python3 src/decision_analysis.py`


Gera análises de:

confiança histórica
distribuição de causas
classificação → causas
cobertura
O resultado é salvo em `data/output/decisao_analise.json`.

Análise Exploratória de Causas Raiz

Windows: `py src/root_cause_analysis.py`

Linux/macOS: `python3 src/root_cause_analysis.py`

Analisa palavras e expressões frequentes por causa raiz para apoiar a revisão de regras. O resultado é salvo em `data/output/causa_raiz_analise.json`; os candidatos exigem validação da equipe N2.

Dicionário de Intenções e Relatório Histórico

O dicionário determinístico é mantido em `data/input/dicionario_aizen_intencoes.yaml`. Para regenerar o relatório baseado no histórico:

Windows: `py src/dictionary_analysis.py`

Linux/macOS: `python3 src/dictionary_analysis.py`

O arquivo `data/output/dicionario_aizen_analise.json` contém frequências, consolidação de causas, aliases, conflitos, dados faltantes, divergências de classificação e intenções priorizadas por volume.

Métricas de Validação Operacional

Após o N2 preencher `Objeto Operacional Validado` e `Classificação Validada` na planilha gerada:

Windows: `py src/validation_analysis.py`

Linux/macOS: `python3 src/validation_analysis.py`

O relatório `data/output/validation_analysis.json` apresenta concordância de classificação, cobertura total e por classificação validada, ambiguidades, concordância por classificação e faixa de confiança, além de erros por regra. Linhas antigas sem status de sugestão são excluídas dos denominadores.

Na planilha, `Concordância` é calculada comparando a classificação sugerida com a validada. As duas colunas de validação são preenchidas manualmente pelo N2. Para calcular cobertura por classe, preencha `Classificação Validada` também em chamados sem sugestão; essa métrica usa somente os chamados rotulados pelo N2.

Padrões sem Sugestão

Gere ou atualize o Plano N2 e execute:

Windows: `py src/uncovered_analysis.py`

Linux/macOS: `python3 src/uncovered_analysis.py`

O relatório `data/output/uncovered_analysis.json` agrupa chamados sem correspondência por expressões compartilhadas, inclui os números para revisão e sinaliza descrições ausentes/curtas. Os agrupamentos são exploratórios: o N2 decide quais padrões justificam novas regras. Se existir um Plano N2 gerado, o relatório também aproveita as classes validadas nele.

Avaliação do Dicionário

Windows: `py src/root_cause_engine.py`

Linux/macOS: `python3 src/root_cause_engine.py`


Métricas:

Cobertura

Acerto de Classe no Histórico

Ambiguidade

Desempenho por classificação


Esses scripts são de análise e não alteram o Plano N2.
Os arquivos gerados em `data/output/` são resultados locais e não são versionados.

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
Causa identificada e causa raiz padrão.
Classificação automática a partir da causa normalizada.
Objeto Operacional Sugerido.
Classificação Sugerida.
Classificação automática sem score numérico.
Exportação automática das sugestões para Excel.
Registro da regra aplicada, estado e ambiguidade da sugestão.
Persistência das validações do N2 entre execuções.
Concordância calculada na planilha.
Métricas de validação operacional em JSON.
O Que Continua Manual

Os seguintes campos continuam dependentes da operação N2:

RESPONSÁVEL
Prioridade
Ofensor
Observação/Ação
Objeto Operacional Validado
Classificação Validada

As sugestões geradas pelo sistema:

Objeto Operacional Sugerido

Classificação Sugerida

Score de Confiança (coluna legada, mantida vazia e fora da decisão)


são apoio à revisão. Quando uma causa é identificada, `Causa raiz` recebe o nome canônico e `Classificação` recebe a classe oficial mapeada. A validação do N2 permanece disponível para medir concordância e revisar casos sem correspondência ou discordantes.

Indicador Principal

O KPI principal da validação operacional é a **Concordância de Classificação**: sugestões validadas pelo N2 que correspondem à classificação sugerida.

O acerto histórico do motor continua sendo acompanhado durante a avaliação das regras, mas não substitui a concordância medida em validações operacionais.

O alvo operacional continua sendo a classificação do trabalho do N2, não a previsão da causa raiz exata.

Próximos Passos
Acumular validações do N2 em chamados novos e rotular também parte dos não cobertos para medir cobertura por classe.
Revisar regras com maior volume de discordâncias antes de ampliar a cobertura.
Revisar periodicamente taxonomia e regras operacionais.
Evoluir a taxonomia apenas após validação do N2.
Resultado Esperado

Quando um novo chamado chega:

Descrição
        ↓
Causa identificada
        ↓
Normalização para causa raiz padrão
        ↓
Classificação oficial


permitindo ao N2 reduzir esforço de triagem e manter consistência operacional.