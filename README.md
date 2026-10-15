# App Kaizen de Perdas

App web para registrar perdas de produção **por máquina e por motivo**, e transformar esse registro em painel com farol e Pareto. Inspirado num projeto Kaizen real que reduziu o desperdício em 30% no primeiro mês.

> Todos os dados deste repositório são **fictícios** (fábrica de embalagens com 10 máquinas).

**App no ar:** [kaizen-perdas-jcmoraes.streamlit.app](https://kaizen-perdas-jcmoraes.streamlit.app)

## Telas

1. **Registro de perda:** o operador informa máquina, turno, material, kg perdidos e o motivo.
2. **Painel:** perda total em kg e R$, perda % contra a meta (4%) e farol verde/amarelo/vermelho por máquina.
3. **Pareto:** perdas por motivo ou por máquina, com % acumulado e leitura automática dos itens que somam 80%.
4. **Diagnóstico + A3:** por máquina, mostra perda por motivo, tendência semanal e tipo de ação sugerida. Um botão gera um rascunho de **relatório A3 com IA** (OpenAI), com Ishikawa, 5 Porquês e plano de ação, que pode ser baixado em Markdown, o plano de ação em CSV (abre no Excel) e os dados completos em JSON.

## Como o A3 com IA funciona

O A3 não é um texto livre da IA. O modelo é obrigado a responder num **JSON que segue um schema** (Structured Outputs da OpenAI, modo `strict`), definido com classes **Pydantic** em `ia_a3.py`. O app recebe campos com tipo garantido e monta o relatório, a tabela e os downloads a partir deles.

O que o schema garante, sem depender de o modelo "obedecer" o prompt:

- **Causas travadas nos dados reais.** O schema é montado na hora para cada máquina: os motivos do Ishikawa, da situação atual e a "causa atacada" de cada ação só aceitam os motivos registrados daquela máquina. A IA não consegue inventar nem renomear uma causa.
- **Ishikawa separado em fatos e hipóteses.** Motivos registrados (com kg e % vindos dos dados) ficam numa lista; causas prováveis de chão de fábrica ficam em outra, sempre marcadas como *hipótese a validar*.
- **Exatamente 5 porquês**, em cinco campos fixos. A causa raiz é o 5º porquê, o que obriga a cadeia a chegar nela.
- **Vocabulário de fábrica controlado.** Categorias 6M, tipo de ação (Operacional / Mecânica / Material) e responsáveis (Supervisor de produção, Líder de turno, Manutenção, Qualidade, PCP, Compras) são listas fechadas.
- **"Outros" não recebe ação inventada.** Como não dá para atacar uma causa sem nome, o próprio app acrescenta a ação de detalhar esses registros.

Os números do contexto (ganho se a meta for atingida, custo por kg, ranking) são calculados em Python e enviados prontos, para a IA não fazer conta de cabeça. Cada A3 fica em cache por 24 h e há um limite de 5 por sessão no app público, para proteger os créditos da API.

## Como rodar

```bash
pip install -r requirements.txt
python gerar_dados.py      # opcional: o app cria a base fictícia sozinho se ela não existir
streamlit run app.py       # abre o app no navegador
```

### Chave da OpenAI (para o A3)

1. Copie `.env.exemplo` para `.env`
2. Coloque a sua chave em `OPENAI_API_KEY=`
3. Reinicie o app

No Streamlit Community Cloud, coloque a chave em **Settings → Secrets**:

```toml
OPENAI_API_KEY = "sua-chave"
OPENAI_MODEL = "gpt-4.1-mini"   # opcional; padrão gpt-4o-mini
```

O modelo precisa ter suporte a Structured Outputs (ex.: `gpt-4o-mini`, `gpt-4.1-mini`, `gpt-4o`). Nos testes, o `gpt-4.1-mini` encadeou melhor os 5 Porquês.

O `.env` está no `.gitignore` e nunca deve ser publicado.

## Estrutura dos dados

| Tabela | Conteúdo |
| --- | --- |
| perdas | Cada apontamento: data, turno, máquina, operador, material, kg, motivo |
| producao | kg utilizado por máquina por dia (base para a perda %) |
| maquinas | AUTO 1 a AUTO 10, meta de perda |
| motivos | Motivo e tipo de ação (Operacional / Mecânica / Material) |
| materiais | Lâmina PET e bobina, com custo por kg |

## Próximas fases

- Exportar o A3 em Word/PDF
- Salvar os A3 gerados e acompanhar o status de cada ação do plano

## Stack

Python · Streamlit · pandas · Plotly · SQLite · OpenAI API (Structured Outputs) · Pydantic