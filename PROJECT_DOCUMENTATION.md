# RAG Enhancer: Telecom Table Routing System

## Project Overview

This project implements a **Retrieval-Augmented Generation (RAG) based routing system** that intelligently routes telecom KPI (Key Performance Indicator) queries to the appropriate database tables. Instead of manually mapping queries to tables, we use semantic understanding through embeddings and LLM reasoning to automatically determine which table(s) can answer a given query.

---

## The Problem We're Solving

### Background

In a telecom data warehouse, there are multiple tables storing different aspects of subscriber data:
- Campaign interactions
- Recharge transactions
- Usage metrics
- Subscriber profiles
- Real-time events
- And more...

When a business user asks a question like:
> "Show me subscribers who received a bonus in the last 30 days"

The system needs to know **which table** contains this information. Manually maintaining these mappings is:
- Error-prone
- Hard to scale
- Requires domain expertise for every query

### Our Solution

We built an intelligent routing system that:
1. **Understands** the semantic meaning of KPI descriptions
2. **Retrieves** relevant table metadata using vector similarity
3. **Reasons** about which table is the best match using an LLM
4. **Evaluates** its confidence and can retry with query rewriting if needed

---

## Architecture

### High-Level Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Step 1:        │     │  Step 2:        │     │  Step 3:        │     │  Step 4:        │
│  Create App     │ ──▶ │  Load Data      │ ──▶ │  Run Routing    │ ──▶ │  Evaluate       │
│  (Validate)     │     │  (From MySQL)   │     │  (LLM + RAG)    │     │  (Metrics)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │                        │
                              ▼                        ▼                        ▼
                        sampled_kpi_data.csv    checkpoint_results.csv    confusion_matrix.png
```

### Components

| Component | File | Purpose |
|-----------|------|---------|
| **App Factory** | `app_factory.py` | Creates the LangGraph routing application with LLM, embeddings, and vector store |
| **Data Loader** | `load_group_kpi_data.py` | Loads KPI data from MySQL database and samples for evaluation |
| **Router** | `run_table_routing_with_checkpoint.py` | Runs the routing logic with checkpoint/resume support |
| **Evaluator** | `evaluate_routing_model.py` | Computes accuracy, confusion matrix, and classification report |
| **Knowledge Base** | `telecom_table_knowledge_base.json` | Metadata about all available tables |

---

## The Knowledge Base

### Structure

Each table in our knowledge base has rich metadata:

```json
{
  "table_id": "T1",
  "table_name": "LIFECYCLE_CDR",
  "description": "This table tracks all campaign and marketing interactions...",
  "data_type": "summarized",
  "time_windows": ["2D", "7D", "30D", "180D", "365D"],
  "refresh": "near real-time",
  "granularity": "one record per subscriber with rolling aggregates",
  "example_queries": [
    "subscribers who did not respond to any campaign in the last 30 days",
    "how many promotions were delivered successfully last week"
  ],
  "never_use_for": "revenue, usage, recharge, demographics, device, plan"
}
```

### Available Tables

| Table | Purpose | Data Type |
|-------|---------|-----------|
| **LIFECYCLE_CDR** | Campaign/marketing interactions, bonus campaigns, promotional tracking | Summarized |
| **360_PROFILE** | Consolidated subscriber view (demographics, usage, revenue, segmentation) | Summarized |
| **AUDIENCE_SEGMENT_CDR** | Campaign audience segment membership mapping | Mapping |
| **Recharge_Seg_Fct** | Prepaid recharge analytics (amounts, channels, frequency) | Summarized + Transaction |
| **Subscriptions** | Product/bundle subscriptions, VAS, roaming packs | Summarized + Event |
| **Profile_Cdr_group** | Master subscriber profile (plan changes, credit rating, dealer) | Profile Attributes |
| **Common_Seg_Fct** | Detailed usage/revenue breakdown (onnet/offnet, ARPU, trends) | Summarized |
| **Instant_cdr_group** | Real-time transactional events (calls, SMS, recharges as they happen) | Real-time |

### Key Insight: `never_use_for` Field

Each table specifies what it should **NOT** be used for. This prevents misrouting:

```json
// LIFECYCLE_CDR
"never_use_for": "revenue, usage, recharge, demographics, device, plan"

// Instant_cdr_group
"never_use_for": "summarized metrics, rolling averages, 30-day aggregates, historical analysis"
```

---

## The LangGraph Routing Flow

### State Machine

```
                    ┌──────────────┐
                    │   START      │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   RETRIEVE   │◀─────────────────┐
                    │  (Vector DB) │                  │
                    └──────┬───────┘                  │
                           │                          │
                           ▼                          │
                    ┌──────────────┐                  │
                    │   EVALUATE   │                  │
                    │    (LLM)     │                  │
                    └──────┬───────┘                  │
                           │                          │
              ┌────────────┼────────────┐             │
              │            │            │             │
              ▼            ▼            ▼             │
         "correct"   "ambiguous"  "incorrect"         │
              │            │            │             │
              │            │            └─────┬───────┤
              │            │                  │       │
              ▼            ▼                  ▼       │
           ┌─────┐     ┌─────┐         ┌──────────┐  │
           │ END │     │ END │         │ REWRITE  │──┘
           └─────┘     └─────┘         │ (max 2x) │
                                       └──────────┘
```

### Node Descriptions

#### 1. Retrieve Node
- Takes the user's KPI description (or rewritten query)
- Uses vector similarity to find the top 5 most relevant table descriptions
- Returns candidate tables for evaluation

#### 2. Evaluate Node
- LLM receives the KPI description + retrieved table metadata
- Applies routing rules (see below)
- Returns structured JSON with:
  - `evaluation`: "correct" | "ambiguous" | "incorrect"
  - `routed_tables`: List of tables with confidence scores
  - `reasoning`: Explanation of the decision

#### 3. Rewrite Node (if needed)
- If evaluation is "incorrect" and retry count < 2
- LLM rewrites the query to be more specific
- Loop back to retrieve with the rewritten query

### Routing Rules (in the LLM Prompt)

```
1. SUMMARIZED data (totals, averages, trends) → NEVER pick Instant_cdr_group
2. REAL-TIME or LATEST EVENT data → pick Instant_cdr_group
3. Campaign, promotion, bonus, delivery, response → LIFECYCLE_CDR
4. Audience segment, segment membership → AUDIENCE_SEGMENT_CDR
5. Recharge amount, denomination, channel, top-up → Recharge_Seg_Fct
6. Product subscription, bundle, VAS → Subscriptions
7. Plan change, credit rating, dealer → Profile_Cdr_group
8. Onnet/offnet voice, ARPU, monthly trend → Common_Seg_Fct
9. Holistic view, demographics + usage, NBO → 360_PROFILE
10. Multiple KPIs mentioned → Return MULTIPLE tables
```

---

## The 4-Step Modular Pipeline

### Why Modular?

Originally, everything ran in a single `main.py`. Problems:
- If step 3 failed after processing 500 rows, you'd lose all progress
- Couldn't inspect intermediate results
- Hard to debug specific steps

### The Solution: Independent Step Files

Each step can be run independently and produces persistent output:

```bash
# Step 1: Validate the routing app works
python step1_create_app.py

# Step 2: Load data from MySQL (or use cached CSV)
python step2_load_data.py

# Step 3: Run routing with checkpoint support
python step3_run_routing.py

# Step 4: Evaluate results
python step4_evaluate.py
```

### Data Flow Between Steps

```
step1_create_app.py
    │
    │ (validates LLM connectivity, no persistent output)
    │
    ▼
step2_load_data.py
    │
    │ ──▶ data/sampled_kpi_data.csv
    │
    ▼
step3_run_routing.py
    │
    │ ◀── reads sampled_kpi_data.csv
    │ ──▶ data/checkpoint_results.csv (updated after EVERY row)
    │
    ▼
step4_evaluate.py
    │
    │ ◀── reads checkpoint_results.csv
    │ ──▶ data/confusion_matrix.png
    │ ──▶ Classification report (console)
```

---

## Checkpoint/Resume System

### The Problem

Processing 1,470 KPIs takes hours (each LLM call takes ~6-10 seconds). If the process crashes or is interrupted:
- Without checkpointing: Lose ALL progress
- With naive checkpointing: Lose progress since last save

### Our Solution

**Save after EVERY processed row:**

```python
for idx in tqdm(rows_to_process, desc="Routing", unit="row"):
    # ... process row with LLM ...

    final_df.at[idx, "table_name"] = table_value
    final_df.at[idx, "reasoning"] = reasoning_value

    # Save immediately after each row
    final_df.to_csv(CHECKPOINT_FILE, index=False)

    time.sleep(random.uniform(2, 3))  # Rate limiting
```

### Resume Behavior

When you rerun `step3_run_routing.py`:

```
🔁 Resuming from checkpoint...
📊 Status: 21 done, 1449 remaining, 1470 total
🚀 Processing 1449 remaining rows...
Routing:   0%|          | 0/1449 [00:00<?, ?row/s]
```

- Loads existing checkpoint
- Counts already-processed rows (where `table_name` is not null)
- Progress bar shows ONLY remaining rows
- Continues from where it left off

### Key Design Decisions

1. **Pre-filter rows to process**: Instead of iterating all rows and skipping, we filter upfront:
   ```python
   rows_to_process = final_df[final_df["table_name"].isna()].index.tolist()
   ```

2. **Save after every row**: CSV write is fast (~10ms), reliability > micro-optimization

3. **Clear progress reporting**: Show done/remaining/total before starting

---

## Evaluation

### Metrics Computed

1. **Accuracy**: Percentage of correctly routed KPIs
2. **Confusion Matrix**: Visual representation of routing patterns
3. **Classification Report**: Precision, recall, F1-score per table

### How Evaluation Works

```python
# Normalize names for comparison
df["actual"] = df["GROUP_NAME"].apply(normalize_name)      # Ground truth
df["predicted"] = df["table_name"].apply(normalize_name)   # Model prediction

# Compute accuracy
accuracy = (df["actual"] == df["predicted"]).mean() * 100
```

### Example Output

```
🎯 Accuracy: 78.45%

📈 Classification Report:

                        precision    recall  f1-score   support

           360_PROFILE       0.82      0.79      0.80       180
       AUDIENCE_SEGMENT      0.75      0.71      0.73       150
        COMMON_SEG_FCT       0.81      0.85      0.83       200
    INSTANT_CDR_GROUP        0.72      0.68      0.70       120
         LIFECYCLE_CDR       0.85      0.88      0.86       350
     PROFILE_CDR_GROUP       0.77      0.74      0.75       170
      RECHARGE_SEG_FCT       0.79      0.82      0.80       160
         SUBSCRIPTIONS       0.74      0.71      0.72       140
```

---

## Examples

### Example 1: Campaign Query → LIFECYCLE_CDR

**Input KPI:**
> "Subscribers who did not respond to any campaign in the last 30 days"

**Routing Process:**
1. **Retrieve**: Finds LIFECYCLE_CDR (campaign tracking), 360_PROFILE (has campaign flags)
2. **Evaluate**: LLM applies Rule 3 (campaign, response → LIFECYCLE_CDR)
3. **Result**:
   ```json
   {
     "evaluation": "correct",
     "routed_tables": [{"table_name": "LIFECYCLE_CDR", "confidence": 0.92}],
     "reasoning": "Query focuses on campaign response behavior (non-responders)"
   }
   ```

### Example 2: Recharge Query → Recharge_Seg_Fct

**Input KPI:**
> "Average recharge amount in the last 90 days"

**Routing Process:**
1. **Retrieve**: Finds Recharge_Seg_Fct, 360_PROFILE (has recharge summary)
2. **Evaluate**: LLM applies Rule 5 (recharge amount → Recharge_Seg_Fct)
3. **Result**:
   ```json
   {
     "evaluation": "correct",
     "routed_tables": [{"table_name": "Recharge_Seg_Fct", "confidence": 0.88}],
     "reasoning": "Query specifically asks about recharge amounts and 90-day window"
   }
   ```

### Example 3: Real-time Query → Instant_cdr_group

**Input KPI:**
> "Did the subscriber just make a recharge?"

**Routing Process:**
1. **Retrieve**: Finds Instant_cdr_group, Recharge_Seg_Fct
2. **Evaluate**: LLM applies Rule 2 (real-time, latest event → Instant_cdr_group)
3. **Result**:
   ```json
   {
     "evaluation": "correct",
     "routed_tables": [{"table_name": "Instant_cdr_group", "confidence": 0.95}],
     "reasoning": "Query uses 'just' indicating real-time event data needed"
   }
   ```

### Example 4: Multi-table Query

**Input KPI:**
> "High-value subscribers with declining data usage who haven't responded to campaigns"

**Routing Process:**
1. **Retrieve**: Finds 360_PROFILE, LIFECYCLE_CDR, Common_Seg_Fct
2. **Evaluate**: LLM identifies multiple KPI aspects
3. **Result**:
   ```json
   {
     "evaluation": "correct",
     "routed_tables": [
       {"table_name": "360_PROFILE", "confidence": 0.85, "matched_kpi_aspect": "high-value, declining usage"},
       {"table_name": "LIFECYCLE_CDR", "confidence": 0.82, "matched_kpi_aspect": "campaign response"}
     ],
     "reasoning": "Query combines value segmentation with campaign behavior"
   }
   ```

---

## Running the Project

### Prerequisites

```bash
# Local Ollama server running on port 11434
ollama serve

# Required models
ollama pull gpt-oss:20b-cloud    # Or your preferred model
ollama pull nomic-embed-text     # For embeddings
```

### Installation

```bash
pip install langchain langchain-openai langchain-chroma langgraph
pip install pandas mysql-connector-python scikit-learn matplotlib tqdm
```

### Execution

```bash
# Full pipeline (original way)
python main.py

# Modular execution (recommended)
python step1_create_app.py    # Validate setup
python step2_load_data.py     # Load from MySQL → CSV
python step3_run_routing.py   # Route with checkpoints
python step4_evaluate.py      # Generate metrics
```

### Resuming After Interruption

```bash
# Just rerun step 3 - it automatically resumes
python step3_run_routing.py

# To start fresh, delete the checkpoint
rm data/checkpoint_results.csv
python step3_run_routing.py
```

---

## Technical Stack

| Component | Technology |
|-----------|------------|
| LLM | Ollama (local) with gpt-oss:20b-cloud |
| Embeddings | nomic-embed-text via Ollama |
| Vector Store | ChromaDB (in-memory) |
| Orchestration | LangGraph (state machine) |
| Data Processing | Pandas |
| Database | MySQL (MAGIK database) |
| Evaluation | scikit-learn |
| Visualization | Matplotlib |

---

## Key Learnings & Decisions

### 1. Why RAG over Fine-tuning?

- **Flexibility**: Can add new tables by updating JSON, no retraining
- **Explainability**: Can see which tables were retrieved and why
- **Cost**: No expensive fine-tuning, uses existing LLM capabilities

### 2. Why LangGraph?

- **Retry logic**: Natural way to implement rewrite → retrieve → evaluate loop
- **State management**: Clean separation of concerns
- **Extensibility**: Easy to add new nodes (e.g., human-in-the-loop)

### 3. Why Checkpoint After Every Row?

- LLM calls are slow (~6-10s each)
- CSV write is fast (~10ms)
- Reliability >> micro-optimization
- Users frequently interrupt long-running processes

### 4. Why Modular Steps?

- Debug individual components
- Inspect intermediate outputs
- Resume from any point
- Cleaner separation of concerns

---

## Future Improvements

1. **Async processing**: Process multiple rows in parallel
2. **Better embeddings**: Fine-tune embedding model on telecom domain
3. **Caching**: Cache LLM responses for identical queries
4. **Web UI**: Dashboard to monitor routing progress and results
5. **Feedback loop**: Use evaluation results to improve prompts

---

## File Structure

```
rag_enhancer/
├── main.py                              # Full pipeline (all steps)
├── step1_create_app.py                  # Validate routing app
├── step2_load_data.py                   # Load data from MySQL
├── step3_run_routing.py                 # Run routing with checkpoints
├── step4_evaluate.py                    # Generate evaluation metrics
├── app_factory.py                       # LangGraph app creation
├── load_group_kpi_data.py               # MySQL data loading
├── run_table_routing_with_checkpoint.py # Core routing logic
├── evaluate_routing_model.py            # Evaluation metrics
├── telecom_table_knowledge_base.json    # Table metadata
├── .gitignore                           # Git ignore rules
├── PROJECT_DOCUMENTATION.md             # This file
└── data/                                # Generated data (gitignored)
    ├── sampled_kpi_data.csv             # Input data from step 2
    ├── checkpoint_results.csv           # Routing results from step 3
    └── confusion_matrix.png             # Evaluation output from step 4
```

---

*Documentation created for the RAG Enhancer project - a semantic routing system for telecom KPI queries.*
