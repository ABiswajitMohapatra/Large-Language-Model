link- https://frontend-1-indol-chi.vercel.app/


🧑‍💻 Agentic AI Chatbot(BiswaLex)

Owner & Trainer: Biswajit Mohapatra

An LLM-based chatbot built with Groq API embeddings, designed to provide intelligent, context-aware responses. It can answer technical queries, FAQs, and support interactive conversations with users.

🎯 Features

✅ Conversational AI capable of understanding natural language queries

✅ Trained on custom documents for domain-specific knowledge

✅ Built with Streamlit for a simple and interactive web interface

✅ Supports multiple users sequentially

✅ Handles technical questions and general knowledge queries

🛠 Tech Stack

Backend: Python

Frontend: Streamlit

Embeddings & LLM: Groq API

Data Storage: Local document indexing

⚡ Installation

Clone the repository:

git clone https://github.com/<your-username>/agentic-ai-chatbot.git


Navigate to the project folder:

cd agentic-ai-chatbot


Install dependencies:

pip install -r requirements.txt


Set your Groq API key as an environment variable:

export GROQ_API_KEY="your_api_key_here"

🚀 Usage

Start the application:

streamlit run app.py


Open the URL shown in the terminal in your browser

Start interacting with the chatbot

💡 Example Technical Questions

Machine Learning:

“Explain the difference between supervised and unsupervised learning.”

“How does gradient descent work in neural networks?”

Algorithms & Data Structures:

“What is the time complexity of the QuickSort algorithm?”

LLM & AI Concepts:

“Explain the concept of embeddings in LLMs.”

“How can I implement a chatbot using Python and Streamlit?”

📊 Architecture Diagram

Here’s a simple flow of the chatbot:

  +----------------+       +------------------+       +----------------+
  | User Queries   | ----> | Streamlit Frontend| ----> | LLM + Groq API |
  +----------------+       +------------------+       +----------------+
                                                        |
                                                        v
                                               +----------------+
                                               | Local Indexing |
                                               +----------------+
                                                        |
                                                        v
                                               +----------------+
                                               | Response to UI |
                                               +----------------+

🤝 Contribution

Contributions are welcome!

Fork the repository, create a branch, and submit a pull request.

Feel free to add more technical FAQs or improve document indexing.
