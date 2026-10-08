"""Simple terminal client for the local agent graph."""

from rich.console import Console
from rich.prompt import Prompt
from langchain_core.messages import HumanMessage

from .agent_system import agent_app
from .database import initialize_database


def main() -> None:
    initialize_database()
    console = Console()
    console.print("Local Enterprise AI Agent (type 'quit' to exit)", style="bold")
    while True:
        message = Prompt.ask("You")
        if message.strip().lower() in {"quit", "exit"}:
            return
        try:
            result = agent_app.invoke({"messages": [HumanMessage(content=message)]})
            console.print(f"[bold cyan]{result.get('active_agent', 'Agent')}[/bold cyan]")
            console.print(result["messages"][-1].content)
        except Exception as error:
            console.print(f"[bold red]Local agent error:[/bold red] {error}")


if __name__ == "__main__":
    main()