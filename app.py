import streamlit as st
import requests
import os
import tempfile
import shutil
import sys
import tiktoken

# Page configuration
st.set_page_config(
    page_title="PDF RAG Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #2e86ab;
        margin-bottom: 1rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
    }
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin-bottom: 2rem;
    }
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 1rem 1rem 0.25rem 1rem;
        margin-left: 3rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: none;
    }
    .assistant-message {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 1rem 1rem 1rem 0.25rem;
        margin-right: 3rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: none;
    }
    .message-header {
        display: flex;
        align-items: center;
        margin-bottom: 0.5rem;
        font-weight: bold;
        font-size: 0.9rem;
    }
    .message-content {
        font-size: 1rem;
        line-height: 1.5;
    }
    .sources-section {
        margin-top: 1rem;
        padding: 0.75rem;
        background: rgba(255, 255, 255, 0.2);
        border-radius: 0.5rem;
        font-size: 0.85rem;
    }
    .source-item {
        padding: 0.25rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    .source-item:last-child {
        border-bottom: none;
    }
    .typing-indicator {
        display: inline-block;
        padding: 1rem 1.5rem;
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        border-radius: 1rem 1rem 1rem 0.25rem;
        margin-right: 3rem;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { opacity: 0.7; }
        50% { opacity: 1; }
        100% { opacity: 0.7; }
    }
</style>
""", unsafe_allow_html=True)

def install_dependencies():
    """Install required system dependencies"""
    try:
        import fitz  # PyMuPDF
        import tiktoken
        return True
    except ImportError:
        st.warning("Installing required dependencies...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pymupdf", "tiktoken"])
            return True
        except:
            return False

def initialize_session_state():
    """Initialize session state variables"""
    if 'qa_chain' not in st.session_state:
        st.session_state.qa_chain = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'vector_db_initialized' not in st.session_state:
        st.session_state.vector_db_initialized = False
    if 'current_pdf' not in st.session_state:
        st.session_state.current_pdf = None
    if 'model_choice' not in st.session_state:
        st.session_state.model_choice = "llama-3.1-8b-instant"
    if 'vector_db_dir' not in st.session_state:
        st.session_state.vector_db_dir = None
    if 'processing_query' not in st.session_state:
        st.session_state.processing_query = False
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ""

def count_tokens(text, model="gpt-3.5-turbo"):
    """Count tokens in text using tiktoken"""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except:
        return len(text) // 4

def load_pdf_with_fallback(file_path):
    """Load PDF using PyMuPDF"""
    try:
        import fitz
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        
        from langchain.schema import Document
        documents = [Document(page_content=text, metadata={"source": "uploaded_pdf"})]
        return documents, True
        
    except Exception as e:
        st.error(f"PDF processing error: {str(e)}")
        return None, False

def setup_rag_system(pdf_file, model_choice):
    """Set up the RAG system with the uploaded PDF"""
    try:
        with st.spinner("🔄 Processing PDF and setting up RAG system..."):
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_file.read())
                temp_path = tmp_file.name

            # Load PDF
            documents, success = load_pdf_with_fallback(temp_path)
            
            if not success:
                return None, False, "Failed to process PDF file"

            # Import CharacterTextSplitter
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            
            # Optimized chunking based on model choice
            if "8b" in model_choice.lower() or "instant" in model_choice.lower():
                chunk_size = 600
                chunk_overlap = 80
            else:
                chunk_size = 800
                chunk_overlap = 100

            # Use RecursiveCharacterTextSplitter for better chunking
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
            )
            
            texts = text_splitter.split_documents(documents)

            if len(texts) == 0:
                return None, False, "No text content found in PDF"

            st.info(f"📊 Created {len(texts)} chunks from the PDF")

            # Initialize embeddings
            from langchain_community.embeddings import HuggingFaceEmbeddings
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )

            # Create a temporary directory for ChromaDB with proper permissions
            vector_db_dir = tempfile.mkdtemp(prefix="chroma_db_")
            os.chmod(vector_db_dir, 0o755)
            
            # Create vector database in temporary directory
            from langchain_chroma import Chroma
            vectordb = Chroma.from_documents(
                documents=texts,
                embedding=embeddings,
                persist_directory=vector_db_dir
            )

            # Create retriever with fewer documents to reduce context size
            retriever = vectordb.as_retriever(search_kwargs={"k": 2})

            # Initialize LLM with optimized settings
            from langchain_groq import ChatGroq
            
            # Model-specific settings
            model_configs = {
                "llama-3.1-8b-instant": {"max_tokens": 2000, "temperature": 0.1},
                "llama-3.2-1b-preview": {"max_tokens": 2000, "temperature": 0.1},
                "llama-3.2-3b-preview": {"max_tokens": 2000, "temperature": 0.1},
                "llama-3.3-70b-versatile": {"max_tokens": 1500, "temperature": 0.1},
                "llama-guard-3-8b": {"max_tokens": 2000, "temperature": 0.1},
                "mixtral-8x7b-32768": {"max_tokens": 2000, "temperature": 0.1}
            }
            
            config = model_configs.get(model_choice, {"max_tokens": 1500, "temperature": 0.1})
            
            llm = ChatGroq(
                model=model_choice,
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
                timeout=30
            )

            # Create QA chain
            from langchain.chains import RetrievalQA
            
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True,
                chain_type_kwargs={"verbose": False}
            )

            # Store the vector DB directory in session state for cleanup
            st.session_state.vector_db_dir = vector_db_dir
            
            # Clean up temporary PDF file
            os.unlink(temp_path)

            return qa_chain, True, f"✅ Successfully processed {len(texts)} chunks from PDF using {model_choice}!"

    except Exception as e:
        # Clean up temp files in case of error
        try:
            if 'temp_path' in locals():
                os.unlink(temp_path)
            if 'vector_db_dir' in locals():
                shutil.rmtree(vector_db_dir, ignore_errors=True)
        except:
            pass
        return None, False, f"❌ Error: {str(e)}"

def cleanup_vector_db():
    """Clean up the vector database directory"""
    if st.session_state.vector_db_dir and os.path.exists(st.session_state.vector_db_dir):
        try:
            shutil.rmtree(st.session_state.vector_db_dir, ignore_errors=True)
            st.session_state.vector_db_dir = None
        except:
            pass

def display_chat_history():
    """Display chat history in a beautiful format"""
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    for i, (role, message, sources) in enumerate(st.session_state.chat_history):
        if role == "user":
            st.markdown(f'''
            <div class="user-message">
                <div class="message-header">👤 You</div>
                <div class="message-content">{message}</div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            # Format sources if available
            sources_html = ""
            if sources and len(sources) > 0:
                sources_list = ""
                for source in set(sources):
                    sources_list += f'<div class="source-item">📄 {source}</div>'
                
                sources_html = f'''
                <div class="sources-section">
                    <div style="font-weight: bold; margin-bottom: 0.5rem;">📚 Sources:</div>
                    {sources_list}
                </div>
                '''
            
            st.markdown(f'''
            <div class="assistant-message">
                <div class="message-header">🤖 Assistant</div>
                <div class="message-content">{message}</div>
                {sources_html}
            </div>
            ''', unsafe_allow_html=True)
    
    # Show typing indicator if processing
    if st.session_state.processing_query:
        st.markdown('''
        <div class="typing-indicator">
            <div class="message-header">🤖 Assistant</div>
            <div class="message-content">Thinking...</div>
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def optimize_query(query):
    """Optimize the query to reduce token usage"""
    optimization_words = [
        "can you", "please", "could you", "would you", "i want to know",
        "tell me about", "explain to me", "i would like to know", "what is",
        "how does", "could you please", "can you please"
    ]
    
    optimized_query = query.lower()
    for word in optimization_words:
        optimized_query = optimized_query.replace(word, "")
    
    optimized_query = " ".join(optimized_query.split())
    return optimized_query.strip()

def get_available_models():
    """Get list of currently available Groq models"""
    return [
        "llama-3.1-8b-instant",
        "llama-3.2-1b-preview",
        "llama-3.2-3b-preview",
        "llama-3.3-70b-versatile",
        "llama-guard-3-8b",
        "mixtral-8x7b-32768"
    ]

def main():
    # Check and install dependencies
    if not install_dependencies():
        st.error("Failed to install required dependencies. Please check the logs.")
        return

    # Initialize session state
    initialize_session_state()
    
    # Header
    st.markdown('<h1 class="main-header">📚 PDF RAG Assistant</h1>', unsafe_allow_html=True)
    st.markdown("### Ask questions about your PDF documents using AI!")

    # Sidebar
    with st.sidebar:
        st.markdown("## 🔧 Configuration")
        
        # API Key input
        groq_api_key = st.text_input(
            "Enter your Groq API Key:",
            type="password",
            value=os.getenv("GROQ_API_KEY", ""),
            help="Get your API key from https://console.groq.com"
        )
        
        if groq_api_key:
            os.environ["GROQ_API_KEY"] = groq_api_key
            st.success("✅ API Key set!")
        else:
            st.warning("⚠️ Please enter your Groq API Key")
        
        # Model selection
        st.markdown("## 🤖 Model Selection")
        available_models = get_available_models()
        
        model_choice = st.selectbox(
            "Choose a model:",
            available_models,
            index=0,
            help="Smaller models are faster and use fewer tokens"
        )
        
        model_descriptions = {
            "llama-3.1-8b-instant": "🚀 Fast & efficient (Recommended)",
            "llama-3.2-1b-preview": "⚡ Very fast, lightweight",
            "llama-3.2-3b-preview": "⚡ Fast, good balance",
            "llama-3.3-70b-versatile": "🎯 High quality (may hit limits)",
            "llama-guard-3-8b": "🛡️ Safety-focused",
            "mixtral-8x7b-32768": "📚 Large context window"
        }
        
        st.info(f"**Selected:** {model_descriptions[model_choice]}")
        
        st.session_state.model_choice = model_choice
        
        st.markdown("---")
        st.markdown("## 📤 Upload PDF")
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type="pdf",
            help="Upload the PDF document you want to query"
        )
        
        if uploaded_file is not None:
            st.info(f"📄 **Selected file:** {uploaded_file.name}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Process PDF", use_container_width=True):
                    # Clean up previous vector DB
                    cleanup_vector_db()
                    
                    with st.spinner("Processing PDF..."):
                        qa_chain, success, message = setup_rag_system(uploaded_file, model_choice)
                        
                        if success:
                            st.session_state.qa_chain = qa_chain
                            st.session_state.vector_db_initialized = True
                            st.session_state.current_pdf = uploaded_file.name
                            st.session_state.chat_history = []
                            st.success(message)
                        else:
                            st.error(message)
            
            with col2:
                if st.button("🗑️ Clear All", use_container_width=True):
                    # Clean up everything
                    cleanup_vector_db()
                    st.session_state.qa_chain = None
                    st.session_state.vector_db_initialized = False
                    st.session_state.current_pdf = None
                    st.session_state.chat_history = []
                    st.session_state.vector_db_dir = None
                    st.session_state.processing_query = False
                    st.session_state.last_query = ""
                    st.rerun()
                    st.success("✅ Cleared all data!")
        
        st.markdown("---")
        st.markdown("## 💡 Sample Questions")
        st.markdown("""
        **Optimized questions:**
        - "SQL basics summary"
        - "Key database concepts" 
        - "Important SQL commands"
        - "Main topics covered"
        - "Practice exercises types"
        """)
        
        # Clear chat button
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.last_query = ""
            st.rerun()

        st.markdown("---")
        st.markdown("## 🛠️ Troubleshooting")
        st.markdown("""
        **If you get errors:**
        1. Use **llama-3.1-8b-instant** 
        2. Ask shorter questions
        3. Click **Clear All** if issues persist
        4. Check API key is valid
        """)

    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("## 💬 Chat Interface")
        
        # Display current PDF info
        if st.session_state.current_pdf:
            st.markdown(f'''
            <div class="info-box">
                📖 Currently analyzing: <strong>{st.session_state.current_pdf}</strong><br>
                🤖 Using model: <strong>{st.session_state.model_choice}</strong>
            </div>
            ''', unsafe_allow_html=True)
        
        # Display chat history
        display_chat_history()
        
        # Chat input with form to prevent duplication
        if st.session_state.vector_db_initialized and st.session_state.qa_chain:
            with st.form("chat_form", clear_on_submit=True):
                query = st.text_input(
                    "Ask a question about your PDF:",
                    placeholder="Type your question here...",
                    key="query_input"
                )
                
                submitted = st.form_submit_button("Send", use_container_width=True)
                
                if submitted and query and query != st.session_state.last_query:
                    st.session_state.processing_query = True
                    st.session_state.last_query = query
                    
                    try:
                        # Optimize query to reduce tokens
                        optimized_query = optimize_query(query)
                        
                        # Get response from RAG system
                        response = st.session_state.qa_chain.invoke({"query": optimized_query})
                        answer = response["result"]
                        
                        # Extract sources
                        sources = []
                        if "source_documents" in response:
                            sources = [doc.metadata.get("source", "Document") for doc in response["source_documents"]]
                        
                        # Add to chat history (only if not duplicate)
                        if not st.session_state.chat_history or st.session_state.chat_history[-1][1] != query:
                            st.session_state.chat_history.append(("user", query, None))
                            st.session_state.chat_history.append(("assistant", answer, sources))
                        
                        st.session_state.processing_query = False
                        st.rerun()
                        
                    except Exception as e:
                        error_msg = str(e)
                        st.session_state.processing_query = False
                        
                        if "413" in error_msg or "too large" in error_msg.lower():
                            st.error("🚫 **Request too large!** Try asking shorter questions.")
                        elif "400" in error_msg or "model_decommissioned" in error_msg:
                            st.error("🚫 **Model deprecated!** Please select a different model.")
                        elif "429" in error_msg or "rate limit" in error_msg.lower():
                            st.error("🚫 **Rate limit exceeded!** Wait a few minutes.")
                        elif "readonly" in error_msg.lower() or "1032" in error_msg:
                            st.error("🚫 **Database error!** Click **Clear All** and try again.")
                        else:
                            st.error(f"Error getting response: {error_msg}")
        else:
            if not groq_api_key:
                st.warning("⚠️ Please enter your Groq API key in the sidebar.")
            elif not uploaded_file:
                st.info("📤 Please upload a PDF file to get started.")
            elif uploaded_file and not st.session_state.vector_db_initialized:
                st.info("🚀 Click 'Process PDF' to initialize the RAG system.")
    
    with col2:
        st.markdown("## 📊 System Status")
        
        # System status cards
        col1, col2 = st.columns(2)
        
        with col1:
            if st.session_state.vector_db_initialized:
                st.success("✅ RAG Ready")
            else:
                st.error("❌ RAG Not Ready")
        
        with col2:
            if groq_api_key:
                st.success("✅ API Key Set")
            else:
                st.error("❌ API Key Missing")
        
        st.markdown("---")
        st.markdown("## 🔧 Features")
        
        st.markdown("""
        - **💬 Beautiful Chat UI**
        - **🎨 Color-coded Messages**
        - **📚 Source Tracking**
        - **⚡ Fast Responses**
        - **🔄 No Duplicates**
        """)
        
        # Chat statistics
        st.markdown("---")
        st.markdown("## 📈 Chat Stats")
        user_messages = len([msg for msg in st.session_state.chat_history if msg[0] == "user"])
        st.metric("Messages Exchanged", user_messages)

if __name__ == "__main__":
    main()