import os
import re
import sqlite3
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import cohere
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_community.retrievers import BM25Retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.retrievers import EnsembleRetriever
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

load_dotenv()

app = FastAPI(title="Smart Media RAG AI API")

# Cross-Origin Resource Sharing (CORS) - ඕනෑම Website එකක සිට Call කිරීමට ඉඩ දීම
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Clients
cohere_client = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))

# Global Retriever Variable
global_retriever = None

def load_existing_retriever():
    persist_dir = "./chroma_db_website"
    if os.path.exists(persist_dir) and len(os.listdir(persist_dir)) > 0:
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vectorstore = Chroma(persist_directory=persist_dir, embedding_function=embeddings)
        existing_data = vectorstore.get()
        if existing_data and existing_data.get("documents"):
            all_splits = [
                Document(page_content=text, metadata=meta if meta else {})
                for text, meta in zip(existing_data["documents"], existing_data["metadatas"])
            ]
            dense_retriever = vectorstore.as_retriever(search_kwargs={"k": 30})
            bm25_retriever = BM25Retriever.from_documents(all_splits)
            bm25_retriever.k = 30
            try:
                return EnsembleRetriever(retrievers=[bm25_retriever, dense_retriever], weights=[0.5, 0.5])
            except Exception:
                return dense_retriever
    return None

@app.on_event("startup")
def startup_event():
    global global_retriever
    global_retriever = load_existing_retriever()
    print("✅ Vector Database and Retriever successfully loaded on startup!")

# Tools Definition
@tool
def search_website_content(query: str) -> str:
    """Use this tool to perform a deep Reranked Hybrid Search across indexed website pages."""
    if not global_retriever:
        return "No website context available."
    initial_docs = global_retriever.invoke(query)
    if not initial_docs:
        return "No relevant website content found."
    doc_contents = [doc.page_content for doc in initial_docs]
    try:
        rerank_response = cohere_client.rerank(
            model="rerank-v3.0", query=query, documents=doc_contents, top_n=5
        )
        results = []
        for hit in rerank_response.results:
            doc = initial_docs[hit.index]
            url = doc.metadata.get("source_url", "https://www.smartannualreport.com")
            title = doc.metadata.get("title", "Smart Media Page")
            results.append(f"Page Title: {title}\nPage URL: {url}\nContent:\n{doc.page_content}")
        return "\n\n---\n\n".join(results)
    except Exception:
        return "\n\n---\n\n".join([f"Page URL: {d.metadata.get('source_url')}\n{d.page_content}" for d in initial_docs[:5]])

@tool
def query_structured_sql_data(query: str) -> str:
    """Read structured summaries of indexed web pages from SQLite DB."""
    try:
        conn = sqlite3.connect("website_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT url, title, extracted_json FROM website_pages")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return "No structured data available."
        return "\n\n".join([f"URL: {r[0]} | Title: {r[1]}\nSummary: {r[2]}" for r in rows])
    except Exception as e:
        return f"Database error: {e}"

tools = [search_website_content, query_structured_sql_data]

# LLM Setup
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are the Official AI Assistant for 'Smart Media (Pvt) Limited'.\n\n"
        "STRICT RULES FOR SERVICES:\n"
        "1. When asked 'what services do you offer?', ALWAYS prioritize Smart Media's 5 Core Homepage Services:\n"
        "   - 1. Strategic Content and Storytelling\n"
        "   - 2. Advisory on Global Frameworks, Standards, and Jurisdictional Compliance\n"
        "   - 3. Investor-Grade Design and Production\n"
        "   - 4. Digital-First and End-to-End HTML Reports (with Interactive PDF-Twins)\n"
        "   - 5. Video Annual Reports\n\n"
        "2. ALWAYS include clickable Markdown source links at the end of every response:\n"
        "   Format: 🔗 **Source:** [Page Title](https://exact-url-here.com)\n"
        "3. If details (like custom pricing) are missing, link to: [Smart Media Contact Us](https://www.smartannualreport.com/contact-us)"
    )),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=8, handle_parsing_errors=True)

def extract_clean_text(output):
    if isinstance(output, str):
        return output
    elif isinstance(output, list):
        return "\n\n".join([str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in output])
    elif isinstance(output, dict) and "text" in output:
        return output["text"]
    return str(output)

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        raw_response = agent_executor.invoke({"input": request.message})
        clean_answer = extract_clean_text(raw_response.get("output", "Unable to process your request."))
        return {"status": "success", "response": clean_answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail="⚠️ Temporary connection issue. Please try again.")