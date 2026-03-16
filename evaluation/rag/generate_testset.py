import asyncio
import os
import sys
import json
import random
from typing import List, Dict, Any, Optional
from pydantic import SecretStr

# Add project root to path
sys.path.append(os.getcwd())

from src.core.config import settings
from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

async def generate_testset(num_questions: int = 10):
    """
    Generates a high-quality RAGAS test set from ingested documents using an LLM.
    """
    print(f"🎬 Generating {num_questions} test triplets from evaluation storage...")
    
    if not settings.OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY is not set. Cannot generate test set.")
        return

    vector_store = VectorStore(
        db_path=settings.EVAL_CHROMA_DB_PATH,
        collection_name=settings.EVAL_CHROMA_COLLECTION_NAME
    )
    graph_store = GraphStore(db_path=settings.EVAL_KUZU_DB_PATH)
    
    # 1. Fetch chunks for sampling
    all_results = vector_store.collection.get(include=["documents", "metadatas"])
    if not all_results or not all_results.get('documents'):
        print("⚠️ No chunks found in evaluation store. Did you run ingest_eval_data.py?")
        return
    
    docs_list = all_results.get('documents')
    if docs_list is None:
        return
    documents = docs_list
    
    meta_list = all_results.get('metadatas')
    if meta_list is None:
        return
    metadatas = meta_list
    
    ids_list = all_results.get('ids')
    if ids_list is None:
        return
    ids = ids_list
    
    indices = list(range(len(documents)))
    random.shuffle(indices)
    sampled_indices = indices[:num_questions]
    
    llm = ChatOpenAI(
        model="gpt-4o", 
        temperature=0.3,
        api_key=SecretStr(settings.OPENAI_API_KEY)
    )
    
    questions = []
    contexts = []
    ground_truths = []
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert software engineer and AI researcher. Use the provided code context to generate a realistic question and a precise ground truth answer. The question should be something a developer would actually ask about this codebase. The answer must be strictly based on the provided context."),
        ("human", "Code Context:\n{context}\n\nArchitectural Context (Graph Relatives):\n{graph_context}\n\nGenerate a JSON object with 'question' and 'ground_truth' fields.")
    ])
    
    chain = prompt | llm
    
    for idx in sampled_indices:
        content = documents[idx]
        meta = metadatas[idx]
        chunk_id = ids[idx]
        
        # 2. Get help from Graph Store for relationship context
        related = graph_store.get_related_chunks(chunk_id, max_hops=1)
        graph_context = ""
        for r in related:
            graph_context += f"- {r['symbol_name']} ({r['chunk_type']})\n"
        
        print(f"  - Generating triplet for: {meta.get('symbol_name', meta.get('source_id'))}")
        
        try:
            response = await chain.ainvoke({
                "context": content,
                "graph_context": graph_context or "No direct relationships found."
            })
            
            # Ensure text is a string
            if isinstance(response.content, str):
                text = response.content.strip()
            else:
                text = str(response.content).strip()

            # Clean up response if it has markdown blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(text)
            questions.append(data["question"])
            contexts.append([content])
            ground_truths.append(data["ground_truth"])
            
        except Exception as e:
            print(f"  ⚠️ Failed to generate triplet for index {idx}: {e}")
            continue

    final_data = {
        "question": questions,
        "contexts": contexts,
        "ground_truth": ground_truths
    }
    
    # Save to evaluation/data/
    output_dir = os.path.join("evaluation", "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "test_set.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2)
        
    print(f"✅ Test set generated with {len(questions)} high-quality triplets.")
    print(f"📍 Saved to: {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate a synthetic test set for RAG evaluation.")
    parser.add_argument("--num_questions", type=int, default=10, help="Number of questions to generate.")
    args = parser.parse_args()
    
    asyncio.run(generate_testset(num_questions=args.num_questions))
