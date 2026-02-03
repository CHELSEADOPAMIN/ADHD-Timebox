import logging
from connectonion import Agent, host

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

# Lazy load orchestrator to avoid timeouts during import/deployment
orchestrator = None


def get_orchestrator():
    global orchestrator
    if orchestrator is None:
        logger.info("Initializing Orchestrator (Lazy)...")
        from agents.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
    return orchestrator


# Define the main agent
# Removed 'description' as it caused TypeError
agent = Agent(name="adhd-tymebox", model="co/gemini-2.5-pro")


# Custom handler to bridge ConnectOnion host with Orchestrator logic
def custom_handle(message):
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = str(message)

    logger.info(f"Processing message: {content}")
    try:
        # Get orchestrator instance (initializes on first request)
        orc = get_orchestrator()
        response = orc.route(content)
        return response
    except Exception as e:
        logger.error(f"Error in routing: {e}")
        return f"系统错误: {str(e)}"


# Monkey patch the agent's handling methods
agent.handle = custom_handle
agent.input = custom_handle

if __name__ == "__main__":
    host(agent)
