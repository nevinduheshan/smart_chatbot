import os
import re
import json
import shutil
import sqlite3
from dotenv import load_dotenv

import cohere
from firecrawl import FirecrawlApp
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

TARGET_URL = "https://www.smartannualreport.com"
DB_FILE = "website_data.db"
CHROMA_DIR = "./chroma_db_website"

# 1. Verification & Reset Folders
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print("🗑️ Removed old SQLite database.")

if os.path.exists(CHROMA_DIR):
    shutil.rmtree(CHROMA_DIR)
    print("🗑️ Removed old Chroma Vector DB directory.")

# 2. SQLite Database Initialization
conn = sqlite3.connect(DB_FILE)
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

# 3. Firecrawl Scraping
print(f"🚀 Scraping full website: {TARGET_URL} via Firecrawl. Please wait...")
firecrawl_app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

try:
    crawl_result = firecrawl_app.crawl(
        url=TARGET_URL,
        limit=20,
        poll_interval=2,
        scrape_options={'formats': ['markdown']},
        exclude_paths=['*/reports/*', '*/annual-report/*']
    )
except Exception as e:
    print(f"❌ Firecrawl Error: {e}")
    exit()

page_data_list = crawl_result.get("data", []) if isinstance(crawl_result, dict) else getattr(crawl_result, "data", [])

if not page_data_list:
    print("❌ No pages scraped. Check your API key or Target URL.")
    exit()

documents = []
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

for page in page_data_list:
    markdown_text = page.get("markdown", "") if isinstance(page, dict) else getattr(page, "markdown", "")
    metadata = page.get("metadata", {}) if isinstance(page, dict) else getattr(page, "metadata", {})
    
    page_url = metadata.get("sourceURL", TARGET_URL) if isinstance(metadata, dict) else TARGET_URL
    page_title = metadata.get("title", "Smart Media Page") if isinstance(metadata, dict) else "Smart Media Page"

    if markdown_text:
        # Create Document for Vector DB
        doc = Document(
            page_content=markdown_text,
            metadata={"source_url": page_url, "title": page_title}
        )
        documents.append(doc)

        # Extract Summary & Save to SQLite
        cursor.execute(
            "INSERT OR REPLACE INTO website_pages (url, title, extracted_json) VALUES (?, ?, ?)",
            (page_url, page_title, json.dumps({"summary": markdown_text[:500]}))
        )
        conn.commit()

conn.close()
print(f"✅ Extracted content from {len(documents)} pages and stored in SQLite.")

# 4. Text Chunking & Vector DB Creation
print("📦 Chunking documents and building Chroma Vector Index...")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
splits = text_splitter.split_documents(documents)

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma.from_documents(
    documents=splits, 
    embedding=embeddings, 
    persist_directory=CHROMA_DIR
)

print(f"🎉 Complete Fresh Build Successful! {len(splits)} chunks indexed into Chroma DB.")