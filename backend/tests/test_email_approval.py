import unittest
from unittest.mock import patch
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from backend.agent_system import agent_app


class EmailApprovalTests(unittest.TestCase):
    def _draft_model_responses(self):
        return [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "draft_email",
                        "args": {
                            "to": "client@example.test",
                            "subject": "Invoice follow-up",
                            "body": "Please review the overdue invoice.",
                        },
                        "id": "draft-call",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="The draft is ready for your review."),
        ]

    def test_rejected_draft_never_sends(self):
        config = {"configurable": {"thread_id": str(uuid4())}}
        with (
            patch("backend.agent_system._invoke_email_model", side_effect=self._draft_model_responses()),
            patch("backend.agent_system.send_approved_email") as send_email,
        ):
            paused = agent_app.invoke(
                {"messages": [HumanMessage(content="Draft an email to a client")]},
                config=config,
            )
            self.assertTrue(paused.get("__interrupt__"))

            result = agent_app.invoke(Command(resume={"approved": False}), config=config)

        send_email.assert_not_called()
        self.assertIn("not sent", result["messages"][-1].content)

    def test_approved_draft_sends_once(self):
        config = {"configurable": {"thread_id": str(uuid4())}}
        with (
            patch("backend.agent_system._invoke_email_model", side_effect=self._draft_model_responses()),
            patch("backend.agent_system.send_approved_email") as send_email,
        ):
            paused = agent_app.invoke(
                {"messages": [HumanMessage(content="Draft an email to a client")]},
                config=config,
            )
            self.assertTrue(paused.get("__interrupt__"))

            result = agent_app.invoke(Command(resume={"approved": True}), config=config)

        send_email.assert_called_once_with(
            {
                "to": "client@example.test",
                "subject": "Invoice follow-up",
                "body": "Please review the overdue invoice.",
            }
        )
        self.assertIn("was sent", result["messages"][-1].content)


if __name__ == "__main__":
    unittest.main()