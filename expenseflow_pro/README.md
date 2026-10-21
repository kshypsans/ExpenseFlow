# ExpenseFlow — Receipt OCR & Expense Manager

A responsive Flask web application for tracking expenses, scanning receipts with OCR, managing monthly budgets, and analyzing spending.

## Features

- **User Authentication:** Registration, login, and password hashing.
- **Receipt OCR:** Extract merchant, amount, date, and category from image and PDF receipts using Tesseract.
- **Expense Management:** Add, edit, delete, search, and filter expenses; export records to CSV.
- **Dashboard & Analytics:** Spending summaries, category breakdowns, monthly trends, and top merchants.
- **Budget Management:** Set monthly category budgets and receive warnings at 80% and 100%, with suggestions to control spending.
- **Responsive UI:** Mobile-friendly design with light and dark themes.

> **Note:** OCR accuracy depends on receipt quality. Always review extracted information before saving. Tesseract OCR must be installed separately.

## Requirements

- Python 3.10+
- Tesseract OCR
- Dependencies listed in `requirements.txt`

## Installation

### Windows

1. Install [Python](https://www.python.org/downloads/).
2. Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).
3. Open the project folder in VS Code.
4. Open the terminal and run:

```bash
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py run.py
```

5. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

### macOS / Linux

Install Python and Tesseract OCR, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

## Running Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Project Structure

```text
expenseflow_pro/
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── main.py
│   ├── models.py
│   ├── ocr.py
│   ├── static/
│   └── templates/
├── tests/
├── .github/workflows/
├── .vscode/
├── requirements.txt
├── requirements-dev.txt
├── setup_windows.bat
├── run_windows.bat
└── run.py
```

## Upload to GitHub

1. Create a new repository on GitHub.
2. Open the project folder in VS Code.
3. Initialize Git if it hasn't already been initialized.
4. Commit your project files.
5. Connect your repository and push your code.

Example commands for a new local Git repository:

```bash
git init
git add .
git commit -m "Initial ExpenseFlow commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the example repository URL with your own. If Git is already initialized or a remote already exists, adjust the commands accordingly.

**Security:** Never upload passwords, `.env` files, secret keys, personal receipts, or local database files. Ensure these are excluded through `.gitignore`.

## License

MIT License — see `LICENSE`.
