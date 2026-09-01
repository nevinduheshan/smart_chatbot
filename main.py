import os
import re
import sqlite3
import json
import traceback
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

def init_sql_db():
    """Ensure SQLite Database Table exists on startup."""
    conn = sqlite3.connect("website_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS website_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            extracted_json TEXT
        )
    """)
    conn.commit()
    conn.close()

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

    search_query = query
    # Phone, Contact හෝ Email ගැන අහනවා නම් Search Query එකට Keywords එකතු කිරීම
    if any(k in query.lower() for k in ["phone", "contact", "number", "call", "email"]):
        search_query += " +94773950883 +94777999921 info@SmartAnnualReport.com contact us"

    initial_docs = global_retriever.invoke(search_query)
    if not initial_docs:
        return "No relevant website content found."

    doc_contents = [doc.page_content for doc in initial_docs]

    try:
        rerank_response = cohere_client.rerank(
            model="rerank-v3.0",
            query=search_query,
            documents=doc_contents,
            top_n=5
        )
        
        results = []
        for hit in rerank_response.results:
            doc = initial_docs[hit.index]
            url = doc.metadata.get("source_url", "https://www.smartannualreport.com")
            title = doc.metadata.get("title", "Smart Media Page")
            results.append(f"Page Title: {title}\nPage URL: {url}\nContent:\n{doc.page_content}")

        return "\n\n---\n\n".join(results)

    except Exception:
        results = []
        for doc in initial_docs[:5]:
            url = doc.metadata.get("source_url", "https://www.smartannualreport.com")
            title = doc.metadata.get("title", "Smart Media Page")
            results.append(f"Page Title: {title}\nPage URL: {url}\nContent:\n{doc.page_content}")
        return "\n\n---\n\n".join(results)
    
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
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are the Official AI Assistant for 'Smart Media (Pvt) Limited'.\n\n"
        "STRICT CONTACT DETAILS RULES:\n"
        "1. ONLY include full contact details (Phone numbers, Email, Physical Addresses) when the user EXPLICITLY asks for contact information, phone numbers, address, or location.\n"
        "2. NEVER append 'Contact Us' sections, phone numbers, or addresses at the end of general answers (such as questions about services, architecture, or technical topics).\n\n"
        "   - Phone Numbers: +94773950883, +94777999921\n"
        "   - Email: info@SmartAnnualReport.com\n"
        "   - Corporate Office: 23/2, Independence Avenue, Colombo 00700, Sri Lanka\n"
        "   - Development Centre: 29/2, Independence Avenue, Colombo 00700, Sri Lanka\n\n"
        "STRICT RULES FOR SERVICES:\n"
        "1. When asked 'what services do you offer?', ALWAYS prioritize Smart Media's 5 Core Homepage Services:\n"
        "   - 1. Strategic Content and Storytelling\n"
        "   - 2. Advisory on Global Frameworks, Standards, and Jurisdictional Compliance\n"
        "   - 3. Investor-Grade Design and Production\n"
        "   - 4. Digital-First and End-to-End HTML Reports (with Interactive PDF-Twins)\n"
        "   - 5. Video Annual Reports\n\n"
        "2. ALWAYS include clickable Markdown source links at the end of every response:\n"
        "   Format: 🔗 **Source:** [Page Title](https://exact-url-here.com)\n"
        "3. If details (like custom pricing) are missing, link to: [Smart Media Contact Us](https://www.smartannualreport.com/contact)"
    )),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=6,            
    handle_parsing_errors=True,     
    early_stopping_method="generate"
)

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

class IndexRequest(BaseModel):
    url: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # Agent එක Call කිරීම
        raw_response = agent_executor.invoke({"input": request.message})
        clean_answer = extract_clean_text(raw_response.get("output", "Unable to process your request."))
        return {"status": "success", "response": clean_answer}
    
    except Exception as e:
        # 🔍 Terminal එකේ හරියටම Error එක කුමක්දැයි Print කිරීම (Debug සඳහා)
        print("\n❌ [ERROR IN AGENT EXECUTOR]:")
        traceback.print_exc()
        print("----------------------------------------\n")
        
        # User ට Clean Fallback Message එකක් යැවීම
        return {
            "status": "error", 
            "response": "⚠️ I encountered an issue processing this complex request. Please try asking in a slightly simpler way or check the API limits."
        }

@app.post("/api/admin/add-url")
async def add_url_endpoint(request: IndexRequest):
    """Crawl a new URL, persist documents to Vector DB & SQLite, and reload memory live."""
    global global_retriever
    
    # 🔒 1. Domain Lock: Smart Media වෙබ් අඩවියට පමණක් සීමා කිරීම
    target_url = request.url.strip()
    if not target_url.startswith("https://www.smartannualreport.com"):
        raise HTTPException(status_code=403, detail="Access Denied: You can only index pages from https://www.smartannualreport.com")

    try:
        firecrawl_app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
        # 2. Limit එක 2කට අඩු කිරීම (මොකද අපි දෙන්නේ Specific Page එකක් නිසා මුළු සයිට් එකම යන්න ඕනේ නෑ)
        crawl_result = firecrawl_app.crawl(
            url=target_url,
            limit=2, 
            poll_interval=2,
            scrape_options={'formats': ['markdown']}
        )
        
        page_data_list = crawl_result.get("data", []) if isinstance(crawl_result, dict) else getattr(crawl_result, "data", [])
        if not page_data_list:
            raise HTTPException(status_code=400, detail="No content scraped from provided URL.")

        documents = []
        conn = sqlite3.connect("website_data.db")
        cursor = conn.cursor()

        for page in page_data_list:
            markdown_text = page.get("markdown", "") if isinstance(page, dict) else getattr(page, "markdown", "")
            page_url = page.get("metadata", {}).get("sourceURL", target_url) if isinstance(page, dict) else target_url
            page_title = page.get("metadata", {}).get("title", "Indexed Page") if isinstance(page, dict) else "Indexed Page"

            if markdown_text:
                documents.append(Document(page_content=markdown_text, metadata={"source_url": page_url, "title": page_title}))
                cursor.execute(
                    "INSERT OR REPLACE INTO website_pages (url, title, extracted_json) VALUES (?, ?, ?)",
                    (page_url, page_title, json.dumps({"summary": markdown_text[:500]}))
                )
        conn.commit()
        conn.close()

        if documents:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
            splits = text_splitter.split_documents(documents)

            persist_dir = "./chroma_db_website"
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            vectorstore = Chroma(persist_directory=persist_dir, embedding_function=embeddings)
            
            vectorstore.add_documents(splits)
            global_retriever = load_existing_retriever()
            
            return {"status": "success", "message": f"Successfully indexed new page from Smart Media!"}
            
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@app.get("/api/admin/stats")
async def get_stats_endpoint():
    """Retrieve indexed page statistics and list for the Dashboard UI."""
    try:
        conn = sqlite3.connect("website_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT url, title FROM website_pages")
        rows = cursor.fetchall()
        conn.close()
        
        urls_list = [{"url": r[0], "title": r[1]} for r in rows]
        return {
            "total_pages": len(urls_list),
            "pages": urls_list
        }
    except Exception:
        return {"total_pages": 0, "pages": []}