# Contrato de classificação

A classificação responde a uma pergunta: **o que o analista vai alterar (ou entregar) depois de ler o chamado?**

Ela não representa o problema do cliente; representa **o tipo de trabalho operacional** que será executado.

```text
Descrição
    ↓
O que o analista vai alterar?
    ↓
NF? Boleto? Cobrança? Contrato? Informação? Faturamento?
    ↓
Classificação
```

Os nomes abaixo são os valores oficiais usados no histórico e na aba `Referencias`.

## Objetos operacionais

Cada classificação corresponde a um objeto operacional (relação 1:1):

| Objeto operacional | Classificação |
|---|---|
| Documento Fiscal | Cancelamento e Reemissão de Nota Fiscal |
| Título Financeiro | Pagamentos, Boletos e Recebimentos |
| Valor Cobrado | Cobrança e Contestação |
| Contrato/Cadastro | Contratos, Comercial e Cadastro |
| Informação/Atendimento | Atendimento Administrativo e Suporte |
| Parâmetro de Faturamento | Faturamento e Obrigações Fiscais |

## Hipótese H1

**É mais fácil identificar o objeto operacional do que a causa raiz.**

Como objeto e classificação são 1:1, identificar o objeto equivale a identificar a classificação. A comparação é entre 6 objetos e as 95 causas históricas (26 após agrupamento).

Evidência preliminar: com as regras em rascunho, o acerto de classificação ficou em torno de 85%, contra cerca de 49% para a causa raiz exata. Esse número vem de 78 chamados respondidos (19% do histórico), com regras calibradas no mesmo histórico.

Para confirmar:

- medir em chamados novos, que não foram usados na calibração;
- comparar com a classe mais frequente, que acerta 37,7% sozinha, porque menos categorias elevam o acerto por construção;
- comparar com a causa canônica (26 grupos), não só com a causa literal.

---

## Cancelamento e Reemissão de Nota Fiscal

**Objeto alterado:** documento fiscal

Tratamento típico: cancelar a NF e, quando necessário, reemitir ou substituir (CNPJ, PO, data de emissão).

---

## Cobrança e Contestação

**Objeto alterado:** valor cobrado

Tratamento típico: conferir a cobrança e ajustar, creditar, cobrar a diferença ou gerar cobrança avulsa.

---

## Pagamentos, Boletos e Recebimentos

**Objeto alterado:** título financeiro

Tratamento típico: reenviar ou atualizar o boleto, prorrogar vencimento ou prazo, trocar conta de recebimento.

---

## Contratos, Comercial e Cadastro

**Objeto alterado:** cadastro ou contrato

Tratamento típico: congelamento, cancelamento de contrato, atualização cadastral, renegociação ou aditivo.

---

## Atendimento Administrativo e Suporte

**Objeto alterado:** nenhum (Informação/Atendimento)

**Objetivo:** responder ou direcionar

Tratamento típico: encaminhar a outra fila, orientar acesso ao portal, encerrar sem solicitação.

---

## Faturamento e Obrigações Fiscais

**Objeto alterado:** regras fiscais ou parâmetros de faturamento

Tratamento típico: ajustar requisito fiscal do cliente, reenviar NF, esclarecer o faturamento.

---

## Indicador de sucesso

O indicador principal é o **acerto de classificação**, não o acerto de causa raiz.
A causa raiz continua sendo registrada, mas não é o alvo de medição.

## Pontos a validar com o N2

1. **Meio × objetivo.** No histórico, 9 de 79 pedidos de "cancelar NF" estão fora de Cancelamento de NF. Exemplos: cancelar a nota porque o setup foi cobrado em duplicidade (Cobrança) e cancelar para emitir em outra data (Pagamentos). Proposta: quando o meio e o objetivo divergem, vale o objetivo.
2. **Atendimento.** O histórico inclui carta de quitação, que entrega um documento. Com o objeto "Informação/Atendimento" ela cabe nesta classe; confirmar com o N2.
3. **Faturamento.** Os 16 chamados misturam reenvio de NF, dúvidas de faturamento e ajustes de parâmetro fiscal. A amostra é pequena; confirmar o escopo.
