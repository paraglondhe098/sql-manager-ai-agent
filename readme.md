# SQL Database Management System with AI Assistant

An intelligent SQL database management system that combines traditional SQL capabilities with AI-powered natural language processing. This system allows users to interact with their databases using both direct SQL queries and natural language commands.

## 🌟 Features

- **Dual Query Interface**
  - Traditional SQL query execution with AI error explanation support.
  - AI agent query execution.
- **Interactive Web UI** powered by Streamlit
- **Smart Query Processing**
  - Automatic query validation
  - Intelligent error handling and suggestions
- **Export Capabilities**
  - Export results as CSV
  - Export results as JSON
- **Query History** tracking
- **Database Information** display

## 🛠️ Technology Stack

- **Backend**
  - Python 3.8+
  - SQLAlchemy (Database ORM)
  - LangChain (AI Integration)
  - PyMySQL (MySQL Connector)
- **Frontend**
  - Streamlit
- **AI Model**
  - Groq LLM (llama3-8b-8192) (configurable)
- **Database**
  - MySQL

## 📋 Prerequisites

- Python 3.8 or higher
- MySQL Server
- Groq API access
- Required Python packages (see `requirements.txt`)

## ⚙️ Installation

1. Clone the repository:
```bash
git https://github.com/paraglondhe098/sql-manager-ai-agent.git
cd sql-manager-ai-agent
```

2. Create and activate a virtual environment (Optional):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your configuration (For testing purpose):
```env
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_HOST=your_host
MYSQL_DATABASE_NAME=your_database
GROQ_API_KEY=your_groq_api_key
```

## 🚀 Usage

1. Start the application:
```bash
streamlit run app.py
```

2. Open your web browser and navigate to `http://localhost:8501`

3. Connect to your database using the sidebar options

4. Choose your preferred query method:
   - **SQL Console**: Direct SQL query execution
   - **AI Assistant**: Natural language query processing

## 💻 Code Structure

```
sql-management-system/
├── app.py                 # Main Streamlit application
├── utils/
│   ├── dbmanager.py      # Database connection and query management
│   ├── agent.py          # AI agent for natural language processing
│   └── __init__.py
├── requirements.txt       # Project dependencies
└── .env                  # Environment variables
```

## 🔒 Security Features

[//]: # (- Query validation to prevent harmful operations)
[//]: # (- Connection pooling)
- Input sanitization
- Secure credential management
- Error handling and recovery



## 🤝 Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/improvement`)
3. Make changes and commit (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Create a Pull Request

## 📝 Example Usage

### SQL Console
```sql
SELECT * FROM users WHERE age > 25;
```

### AI Assistant
```
Show me all users who are over 25 years old
```

Both queries will produce the same result, but the AI Assistant allows for natural language input.

## ⚠️ Important Notes

- Always backup your database before performing write operations
- Test queries in a development environment first
- Keep your environment variables secure
- Monitor query performance with large datasets

## 🔄 Future Improvements

- [ ] Add query result caching
- [ ] Implement comprehensive testing suite
- [ ] Add support for more database types
- [ ] Enhance AI model capabilities
- [ ] Add user authentication
- [ ] Implement query optimization suggestions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

For questions and support, please open an issue in the GitHub repository.

[//]: # (or contact [your-email@example.com]&#40;mailto:your-email@example.com&#41;.)