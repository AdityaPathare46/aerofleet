import os
import shutil
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma

class MissionKnowledgeBase:
    def __init__(self, project_root):
        self.docs_dir = os.path.join(project_root, "data", "docs")
        self.db_dir = os.path.join(project_root, "data", "vector_db")
        
        # Initialize Embedding Model (Runs locally, free)
        # We use a lightweight model for speed
        self.embedding_fn = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        
        self.vector_db = None
        self._initialize_db()

    def _initialize_db(self):
        """
        Loads the Vector DB if it exists, otherwise builds it from PDFs.
        """
        # Check if we have PDFs to ingest
        if not os.path.exists(self.docs_dir):
            os.makedirs(self.docs_dir)
            print("[RAG] Created data/docs/ folder. Please add PDFs there.")
            return

        pdf_files = [f for f in os.listdir(self.docs_dir) if f.endswith(".pdf")]
        
        if not pdf_files:
            print("[RAG] No PDFs found in data/docs. Using internal fallback knowledge.")
            return

        # Check if DB needs rebuilding (simple logic: if DB dir is empty but PDFs exist)
        db_exists = os.path.exists(self.db_dir) and len(os.listdir(self.db_dir)) > 0
        
        if db_exists:
            print("[RAG] Loading existing Vector Database...")
            self.vector_db = Chroma(persist_directory=self.db_dir, embedding_function=self.embedding_fn)
        else:
            print(f"[RAG] Building Knowledge Base from {len(pdf_files)} documents...")
            self._build_database()

    def _build_database(self):
        """
        Reads PDFs, chunks them, and creates the Vector Store.
        """
        # 1. Load PDFs
        loader = PyPDFDirectoryLoader(self.docs_dir)
        documents = loader.load()
        
        if not documents:
            return

        # 2. Split Text (Chunks of 1000 characters)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)
        
        print(f"[RAG] Processed {len(chunks)} text chunks.")

        # 3. Create Vector DB
        # This saves the "Brain" to disk so we don't re-read PDFs every time
        self.vector_db = Chroma.from_documents(
            documents=chunks, 
            embedding=self.embedding_fn,
            persist_directory=self.db_dir
        )
        print("[RAG] Vector Database built and saved.")

    def retrieve_context(self, query):
        """
        Searches the database for info relevant to the user's query.
        """
        if not self.vector_db:
            return "No internal documents available. Relying on general knowledge."
        
        # Search for top 3 most relevant chunks
        results = self.vector_db.similarity_search(query, k=3)
        
        # Combine them into a single context string
        context_text = "\n\n".join([doc.page_content for doc in results])
        
        print(f"[RAG] Retrieved {len(results)} context chunks for query: '{query}'")
        return context_text

    def refresh_knowledge(self):
        """
        Force rebuild of the database (e.g. if user added new PDFs).
        """
        if os.path.exists(self.db_dir):
            shutil.rmtree(self.db_dir)
        self._initialize_db()