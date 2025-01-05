import os
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from langchain_core.tools import tool
import json
import logging
import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class QueryResult:
    """Data class to store query execution results."""
    type: str
    query: str
    result: Optional[pd.DataFrame]


class DBManager:
    def __init__(self, max_rows_out=3,
                 logger=None,
                 sql_user=None, sql_password=None, sql_host=None, database_name=None):
        self.max_rows_out = max_rows_out
        self.result_ = None
        self.logger = logger or self._init_logger()
        self.logger.info("Environment variables loaded successfully!")

        sql_user = sql_user or os.getenv('MYSQL_USER')
        sql_password = sql_password or os.getenv('MYSQL_PASSWORD')
        sql_host = sql_host or os.getenv('MYSQL_HOST')
        self.database_name = database_name or os.getenv('MYSQL_DATABASE_NAME')
        if not (sql_user and sql_password and sql_host):
            raise Exception(
                "Please provide sql_user, sql_password and sql_host or set the environment variables MYSQL_USER, MYSQL_PASSWORD and MYSQL_HOST")

        try:
            self.engine = create_engine(
                f"mysql+pymysql://{sql_user}:{sql_password}@{sql_host}/{self.database_name}"
            )
            self.Session = sessionmaker(bind=self.engine)
            self.logger.info("Connected to the database!")
        except Exception as e:
            self.logger.warning(f"Error connecting to the database: {e}")
            self.engine = None
            self.Session = None

    def _init_logger(self) -> logging.Logger:
        """Initializes and configures a logger for the module.

        Returns:
            logging.Logger: Configured logger instance
        """
        logger = logging.getLogger(f"{self.__class__.__name__}")

        # Only add handlers if none exist to prevent duplicate logging
        if not logger.hasHandlers():
            # Create console handler with formatting
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            # Set default level to INFO
            logger.setLevel(logging.INFO)

        return logger

    def get_info(self):
        res = f"Database name: {self.database_name}\n"
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        res += f"Total tables = {len(tables)}\n"

        for i, table in enumerate(tables):
            res += f"Table-{i + 1} {table}: Columns = ["
            cols = inspector.get_columns(table)
            col_info = []
            for col in cols:
                col_info.append(f"{col['name']} ({col['type']})")
            res += ", ".join(col_info)
            res += "]\n"

        return res.strip()

    def get_info_dict(self):
        res = {'Database': {"name": self.database_name}}
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        res['Database']['num_tables'] = len(tables)
        res['Database']['tables'] = []

        for i, table in enumerate(tables):
            curr_table = {"name": table, "columns": []}
            cols = inspector.get_columns(table)
            for col in cols:
                curr_col = {"name": col['name'], "type": col['type']}
                curr_table['columns'].append(curr_col)
            res['Database']['tables'].append(curr_table)
        return res

    def read_query(self, query):
        with self.engine.connect() as connection:
            return pd.read_sql_query(query, con=connection)

    def write_query(self, query):
        with self.engine.connect() as connection:
            connection.execute(text(query))
            connection.commit()

    @staticmethod
    def is_select_query(query: str) -> bool:
        """
        Validates if the given query is a SELECT query.
        """
        # Check if the query starts with SELECT (case-insensitive) and has no destructive keywords.
        return bool(re.match(r'^\s*SELECT\b', query, re.IGNORECASE))

    @staticmethod
    def is_write_query(query: str) -> bool:
        """
        Validates if the given query is a write operation (INSERT, UPDATE, DELETE, CREATE, DROP).
        """
        # Match queries that begin with specific write operations.
        return bool(re.match(r'^\s*(INSERT|UPDATE|DELETE|CREATE|DROP)\b', query, re.IGNORECASE))

    def get_read_query_tool(self):

        @tool
        def execute_read_query(query: str) -> str:
            """
            Executes a read-only SQL query (SELECT) ->
            Retrieves the result and stores it in the memory in the form of Pandas DataFrame
            and returns the unique ID of the result ->
            Along with the top-k rows of the result in the form of a JSON string.
            """

            if not self.is_select_query(query):
                return "Error: Only SELECT queries are allowed for this tool."

            try:
                result = self.read_query(query)
                self.result_ = QueryResult(type="read", query=query, result=result)

                if len(result) > self.max_rows_out:
                    tbr = json.dumps(result.head(self.max_rows_out).to_dict(orient="list"))
                    msg = f"Note: Only top {self.max_rows_out} rows are shown here. Total rows in the result are: {len(result)}"
                else:
                    tbr = json.dumps(result.to_dict(orient="list"))
                    msg = ""
                return (f"Query executed successfully."
                        f" Here are the top {self.max_rows_out} rows:\n{tbr}."
                        f" {msg}")
            except Exception as e:
                return f"Error executing query: {e}"

        return execute_read_query

    def get_write_query_tool(self):

        @tool
        def execute_write_query(query: str) -> str:
            """
            Execute a SQL write query to create, insert, delete, or update data in the database.
            Returns a success message if the query is executed successfully, otherwise returns the error message.
            """
            if not self.is_write_query(query):
                return "Error: Only INSERT, UPDATE, DELETE, or CREATE queries are allowed for this tool."

            try:
                self.write_query(query)
                self.result_ = QueryResult(type="write", query=query, result=None)
                return "Data written successfully!"
            except Exception as e:
                return f"Error executing query: {e}"

        return execute_write_query

    def close_connection(self):
        """
        SQLAlchemy handles connection pooling automatically.
        You can dispose of the engine if needed.
        """
        if self.engine:
            self.engine.dispose()
            self.logger.info("Database connection disposed.")
