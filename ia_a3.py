"""
Fase 3 - Geração do rascunho de A3 com a API da OpenAI.

A chave é lida, nesta ordem:
  1. st.secrets["OPENAI_API_KEY"]   (Streamlit Cloud)
  2. variável de ambiente / arquivo .env  (computador local)

O modelo pode ser trocado no .env com OPENAI_MODEL=nome-do-modelo.
"""

import os

from dotenv import load_dotenv

load_dotenv()

MODELO_PADRAO = "gpt-4o-mini"
VERSAO_INSTRUCOES = "2"  # aparece na tela para confirmar que a versão nova está rodando

INSTRUCOES = """Você é um especialista em Lean Manufacturing e melhoria contínua (Kaizen)
em indústrias de embalagens. Escreva em português do Brasil, com linguagem objetiva
de chão de fábrica, sem jargão desnecessário.

Com base APENAS nos dados fornecidos, gere um rascunho de relatório A3 em Markdown.
Comece com a linha "# A3 - Redução de perdas - <máquina>" e use exatamente estas seções:

## 1. Contexto
Duas frases: o que a máquina faz e por que ela foi escolhida (posição no ranking).

## 2. Situação atual
Perda em kg, em R$ e em % do material utilizado, comparada com a meta.
Liste os motivos com kg e %. Se a diferença entre turnos for maior que 20%, destaque.

## 3. Meta
Perda abaixo da meta, com o ganho estimado em kg e R$ por mês se a meta for atingida
(calcule a partir dos dados; mostre a conta).

## 4. Análise de causas (Ishikawa)
Use as categorias 6M, nesta grafia: Método, Máquina, Material, Mão de obra, Medição,
Meio ambiente. Coloque cada motivo registrado na categoria certa, com kg e %.
Acrescente causas prováveis de chão de fábrica (ex.: falta de padrão de regulagem,
desgaste de ferramenta, temperatura de aquecimento, variação da chapa), sempre marcadas
como "(hipótese a validar)". Omita uma categoria se não houver nada útil para ela.

## 5. 5 Porquês da causa principal
A causa principal é o motivo com maior kg. Os porquês devem ficar no nível da máquina,
do processo e da operação (como um supervisor experiente perguntaria no chão de fábrica),
terminando numa causa raiz que possa ser corrigida na própria máquina ou no padrão de
trabalho. Não termine em causas genéricas de gestão (falta de planejamento, equipe
sobrecarregada). Marque a sequência como hipótese a validar com o operador.

## 6. Plano de ação
Tabela: Ação | Causa atacada | Tipo (Operacional / Mecânica / Material) | Responsável | Prazo
- Pelo menos uma ação para cada motivo que represente 10% ou mais da perda.
- Ações operacionais: padrão de regulagem, folha de parâmetros, treinamento no posto.
- Ações mecânicas: manutenção, ajuste do ponto da máquina, checklist preventivo.
- Responsáveis realistas de fábrica: Supervisor de produção, Líder de turno,
  Manutenção, Qualidade, PCP, Compras. Treinamento é do Supervisor ou Líder, não do RH.
- Prazos curtos: entre 7 e 30 dias.

## 7. Acompanhamento
Indicador, frequência, como registrar (o próprio app de perdas) e critério de sucesso.

Regras:
- Escreva sempre "perda", nunca "prejuízo", para quantidades em kg.
- Não invente números que não estejam nos dados ou não venham de uma conta mostrada.
- Seja específico para a máquina e para os motivos dela.
"""


def obter_chave() -> str | None:
    try:
        import streamlit as st
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass  # sem secrets.toml: segue para o .env
    return os.getenv("OPENAI_API_KEY")


def obter_modelo() -> str:
    return os.getenv("OPENAI_MODEL", MODELO_PADRAO)


def gerar_a3(resumo: str) -> str:
    """Envia o resumo da máquina para a OpenAI e devolve o A3 em Markdown."""
    from openai import OpenAI

    chave = obter_chave()
    if not chave:
        raise RuntimeError(
            "Chave da OpenAI não encontrada. Crie o arquivo .env com OPENAI_API_KEY=..."
        )

    cliente = OpenAI(api_key=chave)
    resposta = cliente.chat.completions.create(
        model=obter_modelo(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": INSTRUCOES},
            {"role": "user", "content": resumo},
        ],
    )
    return resposta.choices[0].message.content