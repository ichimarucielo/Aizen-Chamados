# Validação do MVP 1

O código pode ser verificado automaticamente. A correção operacional precisa de
classificações independentes do N2. Nenhum campo manual é preenchido pelo motor.

## Piloto

O lote disponível de 157 chamados já participou da calibração: sua revisão é
retrospectiva e não entra na concordância de aceite. O manifesto registra os IDs
conhecidos do monitoramento, do template e do compilado para excluir reutilização.
O piloto inclui todo o próximo lote, sem selecionar resultados favoráveis.

Na ficha, o N2 preenche classificação, objeto quando aplicável, revisor, data,
gravidade e observação. Classificar antes de consultar a aba de sugestões reduz
o efeito de ancoragem. Use `Fora do escopo` quando nenhuma das seis classes se
aplicar; não force um enquadramento. Gravidade: `Nenhum`, `Leve` ou `Crítico`.
Crítico significa tratamento sugerido que pode gerar ação financeira indevida.
Ambíguos e sem sugestão sempre seguem para triagem humana.

## Critérios propostos ao N2

Proposta escolhida por Felipe em 09/10/2026: priorizar a ação explícita.
Assim, cancelar NF por cobrança duplicada continua em Cancelamento e Reemissão
de Nota Fiscal; a cobrança registra o motivo. Dois pedidos operacionais distintos
com candidatos empatados permanecem ambíguos. A convenção aguarda confirmação
do N2 e não representa aprovação dos limites de concordância.

Valores em `data/input/criterios_mvp.yaml`, ainda sem aprovação: 100 chamados
novos revisados; pelo menos 10 por cada classe real e sugerida; concordância
geral de 90%, por classe sugerida de 80%; ao menos um ambíguo e um sem sugestão
revisados; zero erro crítico; todas as fichas completas. São limites operacionais
iniciais, não prova estatística de desempenho futuro. Cobertura não é acurácia.
Não se ajustam limites depois de ver o resultado para fazer o lote passar.

O responsável N2 deve confirmar ou ajustar os limites e registrar nome e data
nos campos de aprovação. Isso muda a versão: congelar nova candidata e gerar
novo snapshot antes do piloto definitivo. A aceitação final exige decisão real
do N2, mesmo quando o relatório indica `APTO PARA ACEITE N2`.

## Execução reproduzível

No WSL, na raiz do projeto, use `.venv/bin/python`. Defina `VERSAO` com o
diretório da candidata registrado no relatório de fechamento.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python src/mvp_release.py --saida data/output/releases/NOVA_CANDIDATA --evidencias data/output/evidencias_tecnicas.json
.venv/bin/python src/mvp_pilot.py --manifesto "$VERSAO/manifesto.json" --entrada data/input/monitoramento.xlsx --snapshot data/output/piloto_novo.csv
.venv/bin/python src/mvp_pilot.py --manifesto "$VERSAO/manifesto.json" --snapshot data/output/piloto_novo.csv --revisao data/output/piloto_novo.csv --relatorio data/output/aceite_novo.json
```

O arquivo de evidências deve registrar os testes efetivamente executados, versões
das dependências e a verificação do pipeline. Não copie um resultado antigo para
uma versão modificada. O congelamento nunca substitui a execução dos testes.

Preencha somente as colunas manuais em uma cópia do CSV; use essa cópia em
`--revisao` e mantenha o original em `--snapshot`. Para a ficha Excel entregue,
`--revisao` aceita a aba `Revisão N2` com cabeçalho na linha 7. Um novo CSV pode
ser aberto diretamente no Excel; IDs e versão devem ser preservados como texto.
O recibo `.meta.json` verifica a integridade do snapshot, e as sugestões da ficha
nunca substituem o snapshot. O código atual também deve corresponder ao manifesto.

O relatório mostra matriz de confusão, erros por regra, concordância por classe,
cobertura e discordâncias por chamado. Não revisados e retrospectivos são
contabilizados separadamente; ausência de validação gera taxa nula, nunca 100%.

O novo CSV oferece `Tempo de Revisão Minutos`, opcional e preenchido pelo N2.
O relatório calcula soma, média e mediana somente para tempos positivos finitos
em chamados novos com revisão completa. Fichas antigas continuam compatíveis.
Tempos ausentes não viram zero. Sem medição de referência da triagem anterior,
esse indicador não comprova economia de tempo.

## Ajustes e fechamento

Para uma discordância confirmada: registrar causa do erro, corrigir regra
generalizável, adicionar teste de regressão, executar a suíte e congelar nova
candidata. Não reaproveitar o lote usado no ajuste como evidência prospectiva.

`src/mvp_release.py` cria manifesto SHA-256 e ZIP do código, testes, dicionário,
critérios e documentação. O ZIP não contém dados dos clientes. A candidata é
preservada localmente; o aceite operacional e a publicação continuam pendentes
até revisão humana. O ambiente verificado é o WSL Ubuntu com a `.venv` existente;
a confirmação de que ele é o ambiente oficialmente adotado cabe ao responsável.
O Excel desktop 16.0, build 20430, foi usado para recalcular e salvar a planilha
saneada: zero erros de fórmula nas dez abas e quatro gráficos preservados.
A conferência operacional pelo N2 continua pendente.

## Saneamento do Excel — 2026-10-09

O exportador aplica `src/workbook_repairs.py` nas próximas execuções. Os seis
erros encontrados na candidata foram tratados sem alterar valores manuais:

- `Compilado chamados!C60`: a causa literal não existe nas referências. A fórmula
  retorna `Revisão N2 pendente`, sem inventar uma classe ou alterar o dicionário.
- `Compilado chamados!V284`: a descrição de origem está vazia. A extração retorna
  vazio; se houver texto sem o marcador esperado, preserva o texto de origem.
- `Panorama!N5:Q5`: contagens diretas substituem referências ao cache inválido da
  tabela dinâmica. A fonte histórica permanece `Compilado chamados!L5:L283`.
  Finalizados passam a ser positivos; A iniciar conta seu próprio status, em vez
  de somar pendentes, andamento e finalizados negativos.

As contagens verificadas são 3 pendentes, 194 finalizados, 4 em andamento e 0 com
o status literal `A INICIAR`. Outros status, como `Em Roteamento`, permanecem
distintos; nenhuma equivalência de negócio foi presumida. Esse painel mantém seu
recorte histórico de 279 linhas, enquanto o compilado contém 411 chamados.
As tabelas dinâmicas históricas não foram reconstruídas: os quatro indicadores
saneados deixam de depender da tabela reduzida à célula B4.

Registros da execução ficam em `data/output/excel_saneado/`, incluindo a cópia
saneada, auditoria do Excel e comparação com a candidata anterior. Os manifests
anteriores continuam preservados; não servem como identificação do código após
este ajuste. O aceite do MVP ainda exige chamados novos, revisão N2 e confirmação
do ambiente oficial.
