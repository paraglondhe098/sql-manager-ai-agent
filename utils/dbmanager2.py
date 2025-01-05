from typing import Optional, List, Dict, Any, Union
import os
import pandas as pd
import logging
import json
import re
from sqlalchemy import create_engine, text, inspect, Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from langchain_core.tools import tool
from dataclasses import dataclass


@dataclass
class QueryResult:
    """Data class to store query execution results."""
    type: str
    query: str
    result: Optional[pd.DataFrame]


class DBManagerError(Exception):
    """Base exception class for DBManager errors."""
    pass


class ConnectionError_(DBManagerError):
    """Raised when database connection fails."""
    pass


class ValidationError(DBManagerError):
    """Raised when query validation fails."""
    pass


class DBManager:
    """
    Database management class that provides secure interaction with MySQL databases.

    Attributes:
        threshold (int): Maximum number of results to store in memory
        remove_amount (int): Number of results to remove when threshold is reached
        max_rows_out (int): Maximum number of rows to return in query results
        database_name (str): Name of the database being managed
        engine (Engine): SQLAlchemy engine instance
        Session (sessionmaker): SQLAlchemy session factory
        results (List[QueryResult]): List of stored query results
        logger (logging.Logger): Logger instance for the class
    """

    def __init__(
            self,
            threshold: int = 20,
            remove_amount: int = 10,
            max_rows_out: int = 100,
            logger: Optional[logging.Logger] = None,
            sql_user: Optional[str] = None,
            sql_password: Optional[str] = None,
            sql_host: Optional[str] = None,
            database_name: Optional[str] = None
    ) -> None:
        """
        Initialize the DBManager with connection parameters and configuration.

        Args:
            threshold: Maximum number of results to store
            remove_amount: Number of results to remove when threshold is reached
            max_rows_out: Maximum number of rows to return in query results
            logger: Custom logger instance
            sql_user: MySQL username
            sql_password: MySQL password
            sql_host: MySQL host address
            database_name: Name of the database to connect to

        Raises:
            ConnectionError_: If database connection fails
            ValueError: If required credentials are missing
        """
        self.threshold = threshold
        self.remove_amount = remove_amount
        self.results: List[QueryResult] = []
        self.max_rows_out = max_rows_out
        self.logger = logger or self._init_logger()

        # Load credentials
        self.sql_user = sql_user or os.getenv('MYSQL_USER')
        self.sql_password = sql_password or os.getenv('MYSQL_PASSWORD')
        self.sql_host = sql_host or os.getenv('MYSQL_HOST')
        self.database_name = database_name or os.getenv('MYSQL_DATABASE_NAME')

        if not all([self.sql_user, self.sql_password, self.sql_host, self.database_name]):
            raise ValueError(
                "Missing database credentials. Please provide all required parameters "
                "or set corresponding environment variables."
            )

        self._init_connection()

    def _init_connection(self) -> None:
        """
        Initialize database connection with SQLAlchemy.

        Raises:
            ConnectionError_: If connection cannot be established
        """
        try:
            connection_url = (
                f"mysql+pymysql://{self.sql_user}:{self.sql_password}"
                f"@{self.sql_host}/{self.database_name}"
            )
            self.engine = create_engine(connection_url, pool_pre_ping=True)
            self.Session = sessionmaker(bind=self.engine)

            # Test connection
            with self.engine.connect():
                self.logger.info("Successfully connected to database")

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to connect to database: {str(e)}")
            raise ConnectionError_(f"Database connection failed: {str(e)}")

    def _init_logger(self) -> logging.Logger:
        """
        Initialize and configure a logger instance.

        Returns:
            logging.Logger: Configured logger instance
        """
        logger = logging.getLogger(f"{self.__class__.__name__}")

        if not logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        return logger

    @staticmethod
    def validate_query(query: str, query_type: str = "read") -> bool:
        """
        Validate SQL query for security and correctness.

        Args:
            query: SQL query string to validate
            query_type: Type of query ('read' or 'write')

        Returns:
            bool: True if query is valid

        Raises:
            ValidationError: If query fails validation
        """
        # Remove comments and standardize whitespace
        clean_query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        clean_query = re.sub(r'--.*$', '', clean_query, flags=re.MULTILINE)
        clean_query = ' '.join(clean_query.split())

        # Basic SQL injection prevention
        dangerous_patterns = [
            r';\s*$',  # Multiple statements
            r'--',  # Comment attacks
            r'/\*',  # Multi-line comments
            r'xp_',  # Extended stored procedures
            r'EXEC\s+',  # Dynamic SQL execution
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, clean_query, re.IGNORECASE):
                raise ValidationError(f"Query contains potentially dangerous pattern: {pattern}")

        # Validate query type
        if query_type == "read":
            if not re.match(r'^\s*SELECT\b', clean_query, re.IGNORECASE):
                raise ValidationError("Only SELECT queries are allowed for read operations")
        elif query_type == "write":
            if not re.match(r'^\s*(INSERT|UPDATE|DELETE|CREATE|DROP)\b', clean_query, re.IGNORECASE):
                raise ValidationError("Only INSERT, UPDATE, DELETE, DROP, or CREATE queries are allowed for write operations")

        return True

    def read_query(self, query: str) -> pd.DataFrame:
        """
        Execute a read (SELECT) query safely.

        Args:
            query: SQL SELECT query to execute

        Returns:
            pd.DataFrame: Query results as a pandas DataFrame

        Raises:
            ValidationError: If query validation fails
            SQLAlchemyError: If query execution fails
        """
        self.validate_query(query, "read")

        try:
            with self.engine.connect() as connection:
                return pd.read_sql_query(query, con=connection)
        except SQLAlchemyError as e:
            self.logger.error(f"Error executing read query: {str(e)}")
            raise

    def write_query(self, query: str) -> None:
        """
        Execute a write (INSERT/UPDATE/DELETE/CREATE) query safely.

        Args:
            query: SQL write query to execute

        Raises:
            ValidationError: If query validation fails
            SQLAlchemyError: If query execution fails
        """
        self.validate_query(query, "write")

        try:
            with self.engine.connect() as connection:
                connection.execute(text(query))
                connection.commit()
        except SQLAlchemyError as e:
            self.logger.error(f"Error executing write query: {str(e)}")
            raise

    def get_info(self) -> str:
        """
        Get formatted string of database schema information.

        Returns:
            str: Formatted database information
        """
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()

            info = [f"Database name: {self.database_name}",
                    f"Total tables = {len(tables)}"]

            for i, table in enumerate(tables, 1):
                cols = inspector.get_columns(table)
                col_info = [f"{col['name']} ({col['type']})" for col in cols]
                info.append(f"Table-{i} {table}: Columns = [{', '.join(col_info)}]")

            return "\n".join(info)

        except SQLAlchemyError as e:
            self.logger.error(f"Error getting database info: {str(e)}")
            raise

    def get_info_dict(self) -> Dict[str, Any]:
        """
        Get database schema information as a dictionary.

        Returns:
            Dict[str, Any]: Database information in dictionary format
        """
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()

            return {
                'Database': {
                    'name': self.database_name,
                    'num_tables': len(tables),
                    'tables': [
                        {
                            'name': table,
                            'columns': [
                                {'name': col['name'], 'type': str(col['type'])}
                                for col in inspector.get_columns(table)
                            ]
                        }
                        for table in tables
                    ]
                }
            }
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting database info dict: {str(e)}")
            raise

    def get_read_query_tool(self):
        """
        Create a tool for executing read queries.

        Returns:
            Callable: Decorated function for executing read queries
        """

        @tool
        def execute_read_query(query: str) -> str:
            """
            Executes a read-only SQL query (SELECT) ->
            Retrieves the result and stores it in the memory in the form of Pandas DataFrame
            and returns the unique ID of the result ->
            Along with the top-k rows of the result in the form of a JSON string.
            Args:
                query: SQL SELECT query to execute

            Returns:
                str: Query execution result message
            """
            self.clear_old_results()
            curr_id = len(self.results)

            try:
                result = self.read_query(query)
                self.results.append(QueryResult(
                    type="Read",
                    query=query,
                    result=result
                ))

                if len(result) > self.max_rows_out:
                    output_data = result.head(self.max_rows_out).to_dict(orient="list")
                    msg = f"Note: Only top {self.max_rows_out} rows are shown here. Total rows: {len(result)}"
                else:
                    output_data = result.to_dict(orient="list")
                    msg = ""

                return (f"Query executed successfully. Result stored with ID: {curr_id}.\n"
                        f"Results:\n{json.dumps(output_data)}.\n{msg}")

            except (ValidationError, SQLAlchemyError) as e:
                return f"Error executing query: {str(e)}"

        return execute_read_query

    def get_write_query_tool(self):
        """
        Create a tool for executing write queries.

        Returns:
            Callable: Decorated function for executing write queries
        """

        @tool
        def execute_write_query(query: str) -> str:
            """
            Execute a SQL write query to create, insert, delete, or update data in the database.
            Returns a success message if the query is executed successfully, otherwise returns the error message.

            Args:
                query: SQL write query to execute

            Returns:
                str: Query execution result message
            """
            try:
                self.write_query(query)
                self.results.append(QueryResult(
                    type="Write",
                    query=query,
                    result=None
                ))
                return "Data written successfully!"

            except (ValidationError, SQLAlchemyError) as e:
                return f"Error executing query: {str(e)}"

        return execute_write_query

    def access_latest_result(self) -> Union[QueryResult, str]:
        """
        Get the most recent query result.

        Returns:
            Union[QueryResult, str]: Latest result or error message
        """
        return self.results[-1] if self.results else "No results available!"

    def access_result(self, result_id: str) -> Union[QueryResult, str]:
        """
        Get a specific query result by ID.

        Args:
            result_id: ID of the result to retrieve

        Returns:
            Union[QueryResult, str]: Requested result or error message
        """
        try:
            return self.results[int(result_id)]
        except (IndexError, ValueError) as e:
            return f"Error accessing result: {str(e)}"

    def clear_old_results(self) -> None:
        """Remove old results when threshold is reached."""
        if len(self.results) > self.threshold:
            self.results = self.results[-(self.threshold - self.remove_amount):]

    def close_connection(self) -> None:
        """Safely close database connection."""
        if self.engine:
            self.engine.dispose()
            self.logger.info("Database connection closed")