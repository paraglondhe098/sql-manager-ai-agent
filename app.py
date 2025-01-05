import streamlit as st
from typing import Optional
import pandas as pd
from utils.dbmanager import DBManager
from utils.agent import SQLAgent, AgentResponse
from dotenv import load_dotenv


def get_model():
    """Return the language model instance"""
    from langchain_groq import ChatGroq  # Replace with actual model import
    llama = "llama3-8b-8192"
    google = "gemma2-9b-it"
    return ChatGroq(model=llama)  # Initialize your LLM model


def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    if not st.session_state.get("begin"):
        load_dotenv()
    if 'agent' not in st.session_state:
        st.session_state.agent = None
    if 'query_history' not in st.session_state:
        st.session_state.query_history = []
    if 'current_result' not in st.session_state:
        st.session_state.current_result = None


def create_connection(sql_user: str, sql_password: str,
                      sql_host: str, database_name: str) -> Optional[DBManager]:
    """Create database connection and return DBManager instance"""
    try:
        db_manager = DBManager(
            sql_user=sql_user,
            sql_password=sql_password,
            sql_host=sql_host,
            database_name=database_name
        )
        return db_manager
    except Exception as e:
        st.error(f"Failed to connect to database: {str(e)}")
        return None


def display_query_result(response: AgentResponse):
    """Display query result in appropriate format"""
    if response.query_mode == "read" and isinstance(response.query_output, pd.DataFrame):
        df = response.query_output
        st.write("Query:")
        st.code(response.query, language="sql")
        st.write("Result:")
        st.dataframe(df, use_container_width=True)

        # Add export buttons
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download CSV",
                csv,
                "query_result.csv",
                "text/csv",
                key='download-csv'
            )
        with col2:
            json_str = df.to_json(orient="records")
            st.download_button(
                "Download JSON",
                json_str,
                "query_result.json",
                "application/json",
                key='download-json'
            )
    elif response.query_mode == "write":
        st.write("Query executed:")
        st.code(response.query, language="sql")
        st.success("Write operation completed successfully")
    elif response.query_mode == "error":
        st.error(response.error_message)
    else:
        st.warning("No result available or invalid result format")


def main():
    st.set_page_config(page_title="SQL Management App", layout="wide")
    initialize_session_state()

    st.title("SQL Database Management System")

    # Connection settings in sidebar
    with st.sidebar:
        st.header("Database Connection")
        sql_user = st.text_input("SQL User", type="default")
        sql_password = st.text_input("SQL Password", type="password")
        sql_host = st.text_input("SQL Host", type="default")
        database_name = st.text_input("Database Name", type="default")

        if st.button("Connect"):
            db_manager = create_connection(sql_user, sql_password, sql_host, database_name)
            if db_manager:
                model = get_model()
                st.session_state.agent = SQLAgent(model, db_manager)
                st.success("Connected successfully!")

        st.divider()
        if st.session_state.agent:
            st.write("Database Info:")
            db_info = st.session_state.agent.manager.get_info()
            st.code(db_info)

    # Main content area
    if st.session_state.agent:
        # Query input section
        st.header("|| SQL console ||")
        query_tabs = st.tabs(["Execute the SQL query 👱‍♂️", "Let AI execute the query 🤖"])

        with query_tabs[0]:
            query = st.text_area("Enter SQL Query", height=100)
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("Execute Query"):
                    try:
                        with st.spinner("Executing query..."):
                            response = st.session_state.agent.get_result_without_agent(query)
                        st.session_state.query_history.append(response.query)
                        st.write("Response:", response.agent_output)
                        st.session_state.current_result = response
                    except Exception as e:
                        st.error(f"Error executing query: {str(e)}")

        with query_tabs[1]:
            nl_input = st.text_area("Describe what you want to do", height=100)
            if st.button("Process Request"):
                try:
                    with st.spinner("Processing request..."):
                        response = st.session_state.agent.get_result(nl_input)
                    st.session_state.query_history.append(response.query)
                    st.write("Response:", response.agent_output)
                    st.session_state.current_result = response
                except Exception as e:
                    st.error(f"Error processing request: {str(e)}")

        # Results section
        st.header("Query Results")
        if st.session_state.current_result:
            display_query_result(st.session_state.current_result)

        # Query History
        with st.expander("Query History"):
            for i, hist_query in enumerate(st.session_state.query_history):
                st.code(f"{i + 1}. {hist_query}", language="sql")

    else:
        st.info("Please connect to a database using the sidebar options.")


if __name__ == "__main__":
    main()
