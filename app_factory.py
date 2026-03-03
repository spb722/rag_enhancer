# app_factory.py

import json
from typing import TypedDict, Literal
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END


def create_app():

    # ==============================
    # LLM + Embeddings (Ollama Local)
    # ==============================

    llm = ChatOpenAI(
        model="gpt-oss:20b-cloud",
        base_url="http://localhost:11434/v1",  # ← local Ollama, NOT api.ollama.com
        api_key="ollama",
        temperature=0,
    )

    embeddings = OpenAIEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        check_embedding_ctx_length=False,  # ← this is the fix
    )

    # ==============================
    # Load Knowledge Base
    # ==============================

    with open("telecom_table_knowledge_base.json", "r") as f:
        tables = json.load(f)

    docs = []

    for table in tables:

        full_text = (
            f"Table: {table['table_name']}\n"
            f"Description: {table['description']}\n"
            f"Data Type: {table['data_type']}\n"
            f"Time Windows: {', '.join(table['time_windows'])}\n"
            f"Granularity: {table['granularity']}\n"
            f"Refresh: {table['refresh']}"
        )

        docs.append(Document(
            page_content=full_text,
            metadata={
                "table_name": table["table_name"],
                "table_id": table["table_id"],
                "data_type": table["data_type"],
                "chunk_type": "description",
                "never_use_for": table["never_use_for"]
            }
        ))

        examples_text = (
            f"Table: {table['table_name']}\n"
            f"Data Type: {table['data_type']}\n"
            f"Example queries:\n"
        )

        for eq in table["example_queries"]:
            examples_text += f"- {eq}\n"

        docs.append(Document(
            page_content=examples_text,
            metadata={
                "table_name": table["table_name"],
                "table_id": table["table_id"],
                "data_type": table["data_type"],
                "chunk_type": "examples"
            }
        ))

    # ==============================
    # Vector Store
    # ==============================

    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="telecom_tables"
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    # ==============================
    # Graph State
    # ==============================

    class State(TypedDict):
        input_statement: str
        retrieved_docs: list
        evaluation: str
        routed_tables: list
        reasoning: str
        retry_count: int
        rewritten_query: str

    # ==============================
    # Nodes
    # ==============================

    def retrieve_node(state: State) -> State:
        query = state.get("rewritten_query") or state["input_statement"]
        docs = retriever.invoke(query)
        state["retrieved_docs"] = docs
        return state


    EVALUATOR_PROMPT = """You are a telecom data table routing evaluator.

TASK: Given a user's KPI statement and retrieved table descriptions, decide which table(s) the statement should route to.

CRITICAL RULES:
1. If the statement asks for SUMMARIZED data (totals, averages, last N days, trends, rolling metrics) → NEVER pick Instant_cdr_group. Pick the appropriate summarized table.
2. If the statement asks for REAL-TIME events, OR mentions loans, debt, wallet merchants, or lifecycle status (Active/Grace) → pick Instant_cdr_group.
3. If the statement mentions campaign, promotion, bonus, delivery, response → pick LIFECYCLE_CDR.
4. If the statement mentions audience segment, segment membership → pick AUDIENCE_SEGMENT_CDR.
5. If the statement mentions recharge amount, denomination, recharge channel, top-up frequency → pick Recharge_Seg_Fct.
6. If the statement mentions Subscription IDs, MSISDN Index, Prepaid/Postpaid line type, Activation Source, OR product/bundle/VAS activations → pick Subscriptions.
7. If the statement asks for human demographics (age/gender), plan migrations (old plan to new plan), credit rating, or device details → pick Profile_Cdr_group.
8. If the statement asks for overall PREPAID SUBSCRIPTION REVENUE, total prepay spending, ARPU, or on-net/off-net usage from bundles → pick Common_Seg_Fct.
9. A statement can mention MULTIPLE KPIs. Return MULTIPLE tables if needed.

Also check the "never_use_for" field of each retrieved table to make sure you are not misrouting.

OUTPUT FORMAT (strict JSON only, no markdown):
{{
  "evaluation": "correct" or "ambiguous" or "incorrect",
  "routed_tables": [
    {{
      "table_name": "...",
      "confidence": 0.0 to 1.0,
      "matched_kpi_aspect": "which part of the statement maps here"
    }}
  ],
  "reasoning": "brief explanation"
}}

evaluation should be:
- "correct" if you are confident (all confidences > 0.75)
- "ambiguous" if some tables could go either way (any confidence between 0.4-0.75)
- "incorrect" if retrieved docs don't seem relevant at all (all confidences < 0.4)
"""


    def evaluate_node(state: State) -> State:

        docs_text = "\n\n".join(
            [doc.page_content for doc in state["retrieved_docs"]]
        )

        response = llm.invoke([
            SystemMessage(content=EVALUATOR_PROMPT),
            HumanMessage(content=f"""
User Statement:
{state['input_statement']}

Retrieved Tables:
{docs_text}

Return structured JSON.
""")
        ])

        try:
            result = json.loads(response.content)
        except:
            state["evaluation"] = "incorrect"
            state["reasoning"] = "Failed to parse JSON"
            state["routed_tables"] = []
            return state

        state["evaluation"] = result.get("evaluation", "incorrect")
        state["reasoning"] = result.get("reasoning", "")
        state["routed_tables"] = result.get("routed_tables", [])

        return state


    REWRITER_PROMPT = """You are a query rewriter for a telecom KPI routing system.

The original query did not retrieve relevant table descriptions. Rewrite it to be more specific about the telecom data being requested.

Focus on making these aspects explicit:
- What metric/KPI is being asked about (revenue, usage, recharge, campaign, subscription, etc.)
- What time granularity (real-time event, daily summary, 30-day rolling, monthly trend)
- What level of detail (aggregated total, breakdown by type, transaction-level)

Return ONLY the rewritten query text, nothing else."""


    def rewrite_node(state: State) -> State:

        response = llm.invoke([
            SystemMessage(content=REWRITER_PROMPT),
            HumanMessage(content=state["input_statement"])
        ])

        state["rewritten_query"] = response.content.strip()
        state["retry_count"] = state.get("retry_count", 0) + 1

        return state


    def route_after_evaluation(state: State) -> Literal["done", "rewrite"]:
        if state["evaluation"] == "incorrect" and state.get("retry_count", 0) < 2:
            return "rewrite"
        return "done"

    # ==============================
    # Build Graph
    # ==============================

    graph = StateGraph(State)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("rewrite", rewrite_node)

    graph.set_entry_point("retrieve")

    graph.add_edge("retrieve", "evaluate")

    graph.add_conditional_edges(
        "evaluate",
        route_after_evaluation,
        {
            "done": END,
            "rewrite": "rewrite"
        }
    )

    graph.add_edge("rewrite", "retrieve")

    app = graph.compile()

    return app
