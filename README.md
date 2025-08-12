# RAGFormers 

![RAGFormers icon](image.png)

## AI-Licitaciones: Intelligent Tender Document Analysis Platform

## 📌 Overview
**AI-Licitaciones** is an AI-powered web platform designed to automate the analysis and comparison of construction tender documents (bidding terms, proposals, and contracts).  
The system uses **OCR** and **Natural Language Processing (NLP)** to extract, classify, validate, and highlight key legal, technical, and financial aspects, enabling faster, more accurate, and risk-aware decision-making.

## 🚀 Key Features
- 📄 **OCR Processing**: Extracts text from both scanned and digital PDFs.  
- 🧠 **Automatic Classification**: Separates content into legal, technical, and economic sections.  
- 🔍 **Contractor Validation**: Checks RUC and legal eligibility via APIs or web scraping.  
- ⚠️ **Risk Detection**: Identifies missing clauses, ambiguities, and inconsistencies.  
- 📊 **Proposal Comparison**: Interactive dashboard with compliance rates, risk indicators, and visual summaries.  
- 🌐 **Multi-file Upload**: Process multiple documents at once with side-by-side analysis.

## 🛠 Tech Stack
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)  
- **Frontend**: [Streamlit](https://streamlit.io/)  
- **NLP**: [spaCy](https://spacy.io/), [Hugging Face Transformers](https://huggingface.co/)  
- **OCR**: [pytesseract](https://github.com/madmaze/pytesseract), [pdfplumber](https://github.com/jsvine/pdfplumber)  
- **Data Processing**: pandas, regex, requests, BeautifulSoup4  

## 🧭 Architecture 
![Architecture photo](frontend/flow.png)

## 📂 Project Structure
```bash

RAGFormers/
├── backend/        # FastAPI server for document processing & analysis
├── frontend/       # Streamlit dashboard
├── models/         # NLP models and rules
├── data/           # Sample documents for testing
├── README.md

```

## ⚙️ Installation
```bash
# Clone repository
git clone https://github.com/JorgeArguello1999/RAGFarmers.git
cd RAGFormers

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
````

## ▶️ Usage

**Run Backend (FastAPI)**:

```bash
uvicorn backend.main:app --reload
```

**Run Frontend (Streamlit)**:

```bash
streamlit run frontend/app.py
```

Then open the provided local URL in your browser.

## 📊 Workflow

1. Upload one or multiple PDF documents (tender documents, proposals, contracts).
2. System applies OCR and extracts text.
3. NLP model classifies sections (legal, technical, economic).
4. Validates contractor RUC via API/scraping.
5. Detects missing, ambiguous, or risky clauses.
6. Displays interactive comparative dashboard.

## 📈 Example Dashboard

![Dashboard Preview](frontend/dashboard_example.png)
![ChatPreview](frontend/chatbot_example.png)

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE.md) file for details.


**Developed by:** \ RAGFormers 🚀