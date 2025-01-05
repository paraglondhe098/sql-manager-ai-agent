from langchain_core.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, \
    MessagesPlaceholder, ChatPromptTemplate
from langchain_core.language_models import BaseLanguageModel
from langchain.agents import create_tool_calling_agent, AgentExecutor
from utils.dbmanager import QueryResult, DBManager
from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class AgentResponse:
    query_mode: str
    query: str
    query_output: Optional[pd.DataFrame]
    agent_output: str
    error_message: Optional[str] = None

    @classmethod
    def from_query_result(cls, query_result: QueryResult, agent_output: str):
        return cls(query_result.type, query_result.query, query_result.result, agent_output)


class SQLAgent:
    def __init__(self, model: BaseLanguageModel, dbmanager: DBManager):
        self.model = model
        self.manager = dbmanager
        self.agent = self._init_agent()

    def get_response(self, user_input: str):
        return self.agent.invoke({'input': user_input, 'db_info': self.manager.get_info_dict()})

    def get_output(self, user_input: str):
        return self.get_response(user_input)['output']

    def get_result(self, user_input: str):
        try:
            agent_output = self.get_output(user_input)
            return AgentResponse.from_query_result(self.manager.result_, agent_output)
        except Exception as e:
            error_explanation = self.model.invoke(f"There was a problem processing user input: {user_input} "
                                                  f"Error message was {e}. Use this info to find out what went wrong: "
                                                  f"{self.manager.get_info_dict()} "
                                                  f" mention the mistake in the input and write the corrected version.").content
            return AgentResponse(query_mode="error", query=user_input, query_output=None,
                                 agent_output="Error in input.", error_message="AI explanation: "+error_explanation)

    def get_result_without_agent(self, query: str):
        try:
            if self.manager.is_select_query(query):
                query_res = self.manager.read_query(query)
                return AgentResponse(query_mode="read", query=query, query_output=query_res, agent_output="No agent used.")
            else:
                query_res = self.manager.write_query(query)
                return AgentResponse(query_mode="write", query=query, query_output=query_res, agent_output="No agent used.")
        except Exception as e:
            error_explanation = self.model.invoke(f"There was a problem processing SQL query: {query} "
                                                  f"Error message was {e}. Use this info to find out what went wrong: "
                                                  f"{self.manager.get_info_dict()} "
                                                  f" mention the mistake in the query and write the corrected version.").content
            return AgentResponse(query_mode="error", query=query, query_output=None,
                                 agent_output="Error in query.", error_message="AI explanation: "+error_explanation)

    @property
    def latest_result(self):
        return self.manager.result_

    def _init_agent(self):
        prompt = (
            "You are an SQL database management assistant with access to tools for executing various queries on the database, "
            "including read (SELECT) and write (INSERT, UPDATE, DELETE, CREATE, DROP) operations. Your role is to assist users by "
            "interpreting their input, generating the appropriate SQL query when necessary, and utilizing the relevant tool to "
            "execute it. Follow these instructions based on the tool's functionality:\n\n"
            "- **Read Tool:** When a read query is executed, provide a success message, explain the query, and, if applicable, "
            "answer the user's question. For example:\n\n"
            "  \"Query executed successfully. Here are the top 3 rows of the retrieved data:\n"
            "  | Column1 | Column2 | ... |\n"
            "  |---------|---------|-----|\n"
            "  | Value1  | Value2  | ... |\n"
            "  | Value1  | Value2  | ... |\n"
            "  | Value1  | Value2  | ... |\n"
            "\n"
            "  This query first ... and then ...\n"
            "  (if a question was asked) The answer to your question is: ...\"\n\n"
            "- **Write Tool:** When a write query is executed, provide the tool's success or failure message, explain how the query was executed, "
            "and, if relevant, answer any questions posed by the user.\n\n"
            "- **No Tool Usage:** If no tool is used, respond directly to the user's question without generating an SQL query.\n\n"
            "Always ensure your responses are clear, concise, and properly formatted. Use the following database information to guide you: {db_info}"
        )

        # prompt = (
        #     "You are a SQL database management assistant. You have access to tools for executing read (SELECT) "
        #     "and write (INSERT, UPDATE, DELETE, CREATE, DROP) queries on the database. Your task is to assist the user "
        #     "by understanding their input, generating the appropriate SQL query if needed, and passing it to the "
        #     "relevant tool. Follow these instructions based on the tool's usage: "
        #     "\n\n"
        #     "- **Read Tool:** If a read query is executed, provide the success message. Explain the query executed. "
        #     " Also answer the question asked if any. "
        #     "For example:\n\n"
        #     f"  \"Query executed successfully. Here are the top 3 rows of all the rows retrieved: \n"
        #     "  | Column1 | Column2 | ... |\n"
        #     "  |---------|---------|-----|\n"
        #     "  | Value1  | Value2  | ... |\n"
        #     "  | Value1  | Value2  | ... |\n"
        #     "  | Value1  | Value2  | ... |\n"
        #     "  \n"
        #     "  This query first ... and then ... \n"
        #     "  (if question was asked) The answer to your question is: ...\""
        #     "- **Write Tool:** If a write query is executed, return only the success or failure message provided by the tool. "
        #     " Also explain how the query is executed. "
        #     " Also answer the question(s) asked (if any). "
        #     "\n\n"
        #     "- **No Tool Usage:** If no tool is used, respond to the user's question directly without generating a SQL query."
        #     "\n\n"
        #     "Always ensure your responses are clear, concise, and formatted appropriately. Use the following database "
        #     "information to assist you: {db_info}"
        # )

        messages = [
            SystemMessagePromptTemplate(prompt=PromptTemplate(input_variables=['db_info'], template=prompt.strip())),
            MessagesPlaceholder(variable_name='chat_history', optional=True),
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=['input'], template='{input}')),
            MessagesPlaceholder(variable_name='agent_scratchpad', optional=True)
        ]
        chat_prompt = ChatPromptTemplate(messages=messages)

        tools = [self.manager.get_read_query_tool(), self.manager.get_write_query_tool()]
        agent = create_tool_calling_agent(self.model, tools, chat_prompt)
        return AgentExecutor(
            agent=agent,
            tools=tools,
            handle_parsing_errors=True,
            max_iterations=5
        )
