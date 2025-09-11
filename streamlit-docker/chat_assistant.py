import streamlit as st
import os
import uuid
import yaml
import sys
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('chat_assistant')

# Security validation - Check for CloudFront header
def validate_request_source():
    """Validate that the request comes through CloudFront"""
    try:
        # Get headers from Streamlit context
        headers = st.context.headers if hasattr(st.context, 'headers') else {}
        
        # Check for CloudFront secret header
        expected_header = f"{os.environ.get('STACK_NAME', 'netops')}-{os.environ.get('AWS_ACCOUNT_ID', '')}-secret"
        cloudfront_secret = headers.get('X-CloudFront-Secret', '')
        
        # In development mode, skip validation
        if os.environ.get('STREAMLIT_ENV') == 'development':
            logger.info("Development mode - skipping CloudFront header validation")
            return True
            
        if cloudfront_secret != expected_header:
            logger.warning(f"Invalid or missing CloudFront header. Expected: {expected_header[:10]}..., Got: {cloudfront_secret[:10] if cloudfront_secret else 'None'}")
            st.error("🚫 Direct access not allowed. Please use the official application URL.")
            st.stop()
            return False
            
        logger.info("CloudFront header validation successful")
        return True
    except Exception as e:
        logger.error(f"Error validating request source: {e}")
        # In case of error, allow access but log the issue
        return True

# Validate request source early
validate_request_source()

# Configure Streamlit for App Runner compatibility
st.set_page_config(
    page_title="Network Operations Assistant",
    layout="wide",
    initial_sidebar_state="expanded"  # Ensure sidebar is always expanded
)

# Add meta tags to prevent caching
no_cache_meta = """
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
"""
st.markdown(no_cache_meta, unsafe_allow_html=True)

# Hide Streamlit branding and make it look more enterprise
# Added timestamp for cache busting
import time
cache_buster = int(time.time())

hide_streamlit_style = f"""
<style>
    /* Cache buster: {cache_buster} */
    
    #MainMenu {{visibility: hidden !important;}}
    footer {{visibility: hidden !important;}}
    header {{visibility: hidden !important;}}
    .stDeployButton {{display:none !important;}}
    .stDecoration {{display:none !important;}}
    .stToolbar {{display:none !important;}}
    #stDecoration {{display:none !important;}}
    
    /* AGGRESSIVE sidebar fixes - prevent collapse completely */
    .css-1d391kg {{min-width: 250px !important; max-width: 350px !important;}}
    .css-1lcbmhc {{min-width: 250px !important; max-width: 350px !important;}}
    .css-17eq0hr {{min-width: 250px !important; max-width: 350px !important;}}
    .css-1cypcdb {{display: block !important; visibility: visible !important;}}
    .css-1lcbmhc {{display: block !important; visibility: visible !important;}}
    
    /* Hide the sidebar collapse button completely */
    .css-1rs6os {{display: none !important;}}
    .css-vk3wp9 {{display: none !important;}}
    .css-1kyxreq {{display: none !important;}}
    button[title="Close sidebar"] {{display: none !important;}}
    button[aria-label="Close sidebar"] {{display: none !important;}}
    
    /* Force sidebar to always be visible */
    .css-1d391kg .css-1rs6os {{display: none !important;}}
    .css-1d391kg .css-vk3wp9 {{display: none !important;}}
    
    /* Alternative sidebar selectors */
    [data-testid="stSidebar"] {{
        display: block !important;
        visibility: visible !important;
        min-width: 250px !important;
    }}
    
    [data-testid="stSidebar"] > div {{
        display: block !important;
        visibility: visible !important;
    }}
    
    /* Hide any collapse/expand buttons */
    [data-testid="stSidebar"] button[kind="header"] {{display: none !important;}}
    [data-testid="stSidebar"] .css-1rs6os {{display: none !important;}}
    
    /* Custom header styling */
    .main-header {{
        background: linear-gradient(90deg, #1f77b4 0%, #2e86ab 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        color: white;
        text-align: center;
    }}
    
    /* Hide "Made with Streamlit" */
    .css-1dp5vir {{display: none !important;}}
    .css-hi6a2p {{display: none !important;}}
    
    /* Custom styling for professional look */
    .stApp > header {{
        background-color: transparent;
    }}
    
    .stApp {{
        background-color: #f8f9fa;
    }}
    
    /* Sidebar styling improvements */
    .css-1lcbmhc .css-1v0mbdj {{
        padding-top: 1rem;
    }}
    
    /* Ensure sidebar content is always visible */
    .css-1lcbmhc .element-container {{
        display: block !important;
        visibility: visible !important;
    }}
    
    /* Force main content to account for sidebar */
    .css-18e3th9 {{
        padding-left: 1rem;
    }}
    
    /* Additional cache busting styles */
    .streamlit-container-{cache_buster} {{
        display: block;
    }}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# JavaScript to completely disable sidebar collapse functionality
disable_sidebar_collapse = f"""
<script>
// Cache buster: {cache_buster}

function disableSidebarCollapse() {{
    // Remove all collapse buttons
    const collapseButtons = document.querySelectorAll('button[title="Close sidebar"], button[aria-label="Close sidebar"], .css-1rs6os, .css-vk3wp9, .css-1kyxreq');
    collapseButtons.forEach(button => {{
        button.style.display = 'none';
        button.disabled = true;
        button.remove();
    }});
    
    // Ensure sidebar is always visible
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    if (sidebar) {{
        sidebar.style.display = 'block';
        sidebar.style.visibility = 'visible';
        sidebar.style.minWidth = '250px';
    }}
    
    // Override any click handlers that might collapse the sidebar
    document.addEventListener('click', function(e) {{
        if (e.target.closest('.css-1rs6os') || 
            e.target.closest('.css-vk3wp9') || 
            e.target.closest('button[title="Close sidebar"]') ||
            e.target.closest('button[aria-label="Close sidebar"]')) {{
            e.preventDefault();
            e.stopPropagation();
            return false;
        }}
    }}, true);
}}

// Run immediately and on DOM changes
disableSidebarCollapse();

// Use MutationObserver to catch dynamically added elements
const observer = new MutationObserver(function(mutations) {{
    mutations.forEach(function(mutation) {{
        if (mutation.addedNodes.length > 0) {{
            disableSidebarCollapse();
        }}
    }});
}});

// Start observing
observer.observe(document.body, {{
    childList: true,
    subtree: true
}});

// Also run on window load and resize
window.addEventListener('load', disableSidebarCollapse);
window.addEventListener('resize', disableSidebarCollapse);

// Force sidebar to stay open every 100ms for the first 5 seconds
let forceCount = 0;
const forceInterval = setInterval(() => {{
    disableSidebarCollapse();
    forceCount++;
    if (forceCount > 50) {{ // Stop after 5 seconds
        clearInterval(forceInterval);
    }}
}}, 100);

</script>
"""

st.markdown(disable_sidebar_collapse, unsafe_allow_html=True)

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.utils.bedrock_agent import agents_helper
from config import bot_configs
from ui_utils import invoke_agent

def initialize_session():
    """Initialize session state and bot configuration."""
    logger.info("Initializing session state")
    
    # Log credential status at session initialization
    try:
        from credential_manager import log_credential_status
        logger.info("=== SESSION INITIALIZATION ===")
        log_credential_status()
    except Exception as e:
        logger.warning(f"Could not log credential status during initialization: {e}")
    
    if 'count' not in st.session_state:
        st.session_state['count'] = 1
        logger.info("First time initialization")

        # Refresh agent IDs and aliases
        for idx, config in enumerate(bot_configs):
            try:
                logger.info(f"Getting agent ID for {config['agent_name']}")
                agent_id = agents_helper.get_agent_id_by_name(config['agent_name'])
                agent_alias_id = agents_helper.get_agent_latest_alias_id(agent_id)
                bot_configs[idx]['agent_id'] = agent_id
                bot_configs[idx]['agent_alias_id'] = agent_alias_id
                logger.info(f"Found agent ID: {agent_id}, alias ID: {agent_alias_id}")
            except Exception as e:
                logger.error(f"Could not find agent named: {config['agent_name']}, error: {str(e)}")
                continue

        # Get bot configuration
        bot_name = os.environ.get('BOT_NAME', 'Test Assistant')
        logger.info(f"Using bot name: {bot_name}")
        bot_config = next((config for config in bot_configs if config['bot_name'] == bot_name), None)
        
        if bot_config:
            logger.info(f"Found bot configuration: {bot_config['bot_name']}")
            st.session_state['bot_config'] = bot_config
            
            # Load tasks if any
            task_yaml_content = {}
            if 'tasks' in bot_config:
                logger.info(f"Loading tasks from {bot_config['tasks']}")
                try:
                    with open(bot_config['tasks'], 'r') as file:
                        task_yaml_content = yaml.safe_load(file)
                    logger.info(f"Loaded {len(task_yaml_content)} tasks")
                except Exception as e:
                    logger.error(f"Error loading tasks: {str(e)}")
            st.session_state['task_yaml_content'] = task_yaml_content

            # Initialize session ID and message history
            st.session_state['session_id'] = str(uuid.uuid4())
            logger.info(f"Generated session ID: {st.session_state['session_id']}")
            st.session_state.messages = []
        else:
            logger.error(f"Bot configuration not found for {bot_name}")

def main():
    """Main application flow."""
    logger.info("Starting main application flow")
    initialize_session()

    # Display chat interface
    st.title(st.session_state['bot_config']['bot_name'])
    
    # Add application information sidebar
    with st.sidebar:
        st.header("ℹ️ About This Application")
        
        st.markdown("""
        **Network Operations Assistant**
        
        An intelligent AI-powered assistant for network operations monitoring and management.
        """)
        
        st.subheader("🚀 Key Features")
        st.markdown("""
        • **Real-time Network Monitoring** - Query active alarms and performance metrics
        • **Maintenance Schedule Management** - Check ongoing and upcoming maintenance
        • **Performance Analysis** - Analyze KPIs and identify anomalies
        • **Multi-Agent Architecture** - Specialized agents for different tasks
        """)
        
        st.subheader("💡 Example Queries")
        
        # Use regular markdown instead of expanders to avoid sidebar collapse issues
        st.markdown("**Site Information:**")
        st.markdown("""
        • "What's the status of site_dallas_001?"
        • "Show me all sites in Atlanta"
        • "Give me an overview of site_birmingham_003"
        """)
        
        st.markdown("**Maintenance:**")
        st.markdown("""
        • "Is there any ongoing maintenance at site_dallas_002?"
        • "Show me upcoming maintenance for site_birmingham_004"
        • "When is the next scheduled maintenance?"
        """)
        
        st.markdown("**Alarms & Performance:**")
        st.markdown("""
        • "Are there any critical alarms active right now?"
        • "How is site_ridgeland_005 performing?"
        • "Show me throughput metrics for site_dallas_003"
        """)
        
        # Add spacing before session info
        st.markdown("---")
        
        st.subheader("🔧 Session Info")
        try:
            # Get session information
            session_id = st.session_state.get('session_id', 'Not available')
            bot_name = st.session_state['bot_config']['bot_name']
            
            # Create a clean info display
            info_lines = []
            
            # Session ID (show more characters)
            if session_id != 'Not available':
                info_lines.append(f"**Session:** `{session_id[:12]}...`")
            
            # Agent name (shortened if too long)
            if len(bot_name) > 30:
                short_name = bot_name[:27] + "..."
                info_lines.append(f"**Agent:** {short_name}")
            else:
                info_lines.append(f"**Agent:** {bot_name}")
            
            # Agent ID (better formatting)
            if 'agent_id' in st.session_state['bot_config']:
                agent_id = st.session_state['bot_config']['agent_id']
                logger.info(f"Full Agent ID: {agent_id}")
                
                if len(agent_id) > 20:
                    # Show first 6 and last 6 for long AWS IDs
                    display_id = f"{agent_id[:6]}...{agent_id[-6:]}"
                    info_lines.append(f"**Agent ID:** `{display_id}`")
                else:
                    info_lines.append(f"**Agent ID:** `{agent_id}`")
            
            # Display all info lines
            for line in info_lines:
                st.markdown(line)
                
        except Exception as e:
            logger.error(f"Error displaying session info: {e}")
            st.markdown("*Session information unavailable*")
        
        # Add some spacing
        st.markdown("---")
        
        st.subheader("📚 Help & Support")
        st.markdown("""
        For assistance with queries or technical issues, please refer to the documentation or contact your system administrator.
        """)
        
        # Optional: Add a reset session button
        if st.button("🔄 Reset Session", help="Clear chat history and start a new session"):
            # Clear session state
            for key in list(st.session_state.keys()):
                if key not in ['bot_config', 'task_yaml_content']:  # Keep essential config
                    del st.session_state[key]
            st.session_state['session_id'] = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()
    
    # Show message history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle user input
    if 'user_input' not in st.session_state:
        next_prompt = st.session_state['bot_config']['start_prompt']
        logger.info(f"Setting initial prompt: {next_prompt}")
        user_query = st.chat_input(placeholder=next_prompt, key="user_input")
        st.session_state['bot_config']['start_prompt'] = " "
    elif st.session_state.count > 1:
        user_query = st.session_state['user_input']
        
        if user_query:
            logger.info(f"Processing user query: {user_query}")
            
            # Log credential status before processing query
            try:
                from credential_manager import log_credential_status
                logger.info("=== BEFORE PROCESSING USER QUERY ===")
                log_credential_status()
            except Exception as e:
                logger.warning(f"Could not log credential status before query: {e}")
            
            # Display user message
            st.session_state.messages.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            # Get and display assistant response
            response = ""
            with st.chat_message("assistant"):
                try:
                    logger.info("Invoking agent")
                    session_id = st.session_state['session_id']
                    response = st.write_stream(invoke_agent(
                        user_query, 
                        session_id, 
                        st.session_state['task_yaml_content']
                    ))
                    logger.info("Agent invocation completed")
                    
                    # Log credential status after successful completion
                    try:
                        from credential_manager import log_credential_status
                        logger.info("=== AFTER SUCCESSFUL QUERY PROCESSING ===")
                        log_credential_status()
                    except Exception as e:
                        logger.warning(f"Could not log credential status after query: {e}")
                        
                except Exception as e:
                    logger.error(f"Error invoking agent: {str(e)}", exc_info=True)
                    
                    # Log credential status on error
                    try:
                        from credential_manager import log_credential_status
                        logger.error("=== AFTER FAILED QUERY PROCESSING ===")
                        log_credential_status()
                    except Exception as e2:
                        logger.warning(f"Could not log credential status after error: {e2}")
                    
                    st.error(f"An error occurred: {str(e)}")  # Show error in UI
                    response = "I encountered an error processing your request. Please try again."

            # Update chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
            logger.info("Updated chat history")

        # Reset input
        user_query = st.chat_input(placeholder=" ", key="user_input")

    # Update session count
    st.session_state['count'] = st.session_state.get('count', 1) + 1
    logger.info(f"Session count: {st.session_state['count']}")

if __name__ == "__main__":
    logger.info("Starting chat assistant application")
    main()
