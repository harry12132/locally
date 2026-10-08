"""Supervisor and local-data specialist agents."""

import json
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from .database import find_invoices, search_contracts
from .email_action import send_approved_email


llm = ChatOllama(model="qwen2.5:3b", temperature=0, num_ctx=2048)


@tool
def check_invoice_status(client_name: str) -> str:
    """Look up local invoice status, amount, and due date for a client."""
    invoices = find_invoices(client_name)
    if not invoices:
        return json.dumps({"client": client_name, "invoices": [], "message": "No records found."})
    return json.dumps({"client": client_name, "invoices": invoices})


@tool
def search_legal_contracts(query: str) -> str:
    """Search locally stored contract titles and clauses for matching terms."""
    results = search_contracts(query)
    return json.dumps({"query": query, "contracts": results})


@tool
def draft_email(to: str, subject: str, body: str) -> str:
    """Prepare an email draft for explicit human review before sending."""
    return json.dumps({"to": to, "subject": subject, "body": body})


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next_step: Literal["finance", "legal", "email", "end"]
    active_agent: str
    email_draft: dict[str, str]


def _run_specialist(state: AgentState, specialist: str, bound_llm, available_tools):
    instructions = {
        "Accounting Subagent": (
            "You are an Accounting Subagent. Use invoice tools for financial lookups. "
            "If no client is specified, check Smith & Co. Clearly report client, status, amount, and due date."
        ),
        "Legal Subagent": (
            "You are a Legal Subagent. Use local contract search for questions about clauses or terms. "
            "Distinguish retrieved contract text from legal advice."
        ),
    }
    messages = [SystemMessage(content=instructions[specialist]), *state["messages"]]
    response = bound_llm.invoke(messages)
    output_messages: list[BaseMessage] = [response]

    for tool_call in response.tool_calls:
        tool_output = available_tools[tool_call["name"]].invoke(tool_call["args"])
        output_messages.append(
            ToolMessage(content=tool_output, tool_call_id=tool_call["id"])
        )

    if response.tool_calls:
        output_messages.append(bound_llm.invoke([*messages, *output_messages]))

    return {"messages": output_messages, "active_agent": specialist}


finance_llm = llm.bind_tools([check_invoice_status])
legal_llm = llm.bind_tools([search_legal_contracts])
email_llm = llm.bind_tools([draft_email])


def _invoke_email_model(messages):
    return email_llm.invoke(messages)


def finance_subagent(state: AgentState):
    return _run_specialist(
        state,
        "Accounting Subagent",
        finance_llm,
        {"check_invoice_status": check_invoice_status},
    )


def legal_subagent(state: AgentState):
    return _run_specialist(
        state,
        "Legal Subagent",
        legal_llm,
        {"search_legal_contracts": search_legal_contracts},
    )


def email_subagent(state: AgentState):
    messages = [
        SystemMessage(
            content=(
                "You draft professional business emails. Call the draft_email tool with the "
                "recipient address, subject, and complete body. Never claim an email was sent."
            )
        ),
        *state["messages"],
    ]
    response = _invoke_email_model(messages)
    output_messages: list[BaseMessage] = [response]
    draft = None
    for tool_call in response.tool_calls:
        arguments = tool_call["args"]
        draft = {
            "to": str(arguments["to"]),
            "subject": str(arguments["subject"]),
            "body": str(arguments["body"]),
        }
        output_messages.append(
            ToolMessage(content=draft_email.invoke(arguments), tool_call_id=tool_call["id"])
        )
    if response.tool_calls:
        output_messages.append(_invoke_email_model([*messages, *output_messages]))
    return {
        "messages": output_messages,
        "active_agent": "Email Drafting Subagent",
        "next_step": "email" if draft else "end",
        "email_draft": draft or {},
    }


def email_approval_node(state: AgentState):
    draft = state["email_draft"]
    decision = interrupt({"action": "send_email", **draft})
    if not decision.get("approved", False):
        return {
            "messages": [AIMessage(content="The email draft was not sent.")],
            "active_agent": "Email Drafting Subagent",
        }

    send_approved_email(draft)
    return {
        "messages": [AIMessage(content=f"The email to {draft['to']} was sent.")],
        "active_agent": "Email Drafting Subagent",
    }


def supervisor_node(state: AgentState):
    last_message = str(state["messages"][-1].content).lower()
    if any(word in last_message for word in ("email", "e-mail", "send a message", "draft a message")):
        return {"next_step": "email", "active_agent": "Supervisor"}
    if any(word in last_message for word in ("invoice", "balance", "paid", "due", "unpaid", "pay", "client", "amount")):
        return {"next_step": "finance", "active_agent": "Supervisor"}
    if any(word in last_message for word in ("contract", "legal", "clause", "terms")):
        return {"next_step": "legal", "active_agent": "Supervisor"}

    response = llm.invoke(state["messages"])
    return {
        "messages": [response],
        "next_step": "end",
        "active_agent": "Supervisor",
    }


workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("legal", legal_subagent)
workflow.add_node("finance", finance_subagent)
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges(
    "supervisor",
    lambda state: state["next_step"],
    {"finance": "finance", "legal": "legal", "email": "email", "end": END},
)
workflow.add_edge("legal", END)
workflow.add_edge("finance", END)
workflow.add_node("email", email_subagent)
workflow.add_conditional_edges(
    "email",
    lambda state: state["next_step"],
    {"email": "email_approval", "end": END},
)
workflow.add_node("email_approval", email_approval_node)
workflow.add_edge("email_approval", END)

agent_app = workflow.compile(checkpointer=MemorySaver())