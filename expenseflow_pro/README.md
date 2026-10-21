# ExpenseFlow Pro — Receipt OCR & Expense Manager

A responsive Flask expense-management web app with receipt OCR, editable extraction review, spending charts, category budgets, manual expense entry, CSV export, login/registration, and light/dark mode. It is organized as a normal Python project so you can open the folder in Visual Studio Code and publish it to your own GitHub repository.

Inspired by the feature list of [Ayushmita24/ocr-expense-tracker](https://github.com/Ayushmita24/ocr-expense-tracker). This project is a separate implementation with additional budget, manual-entry, analytics, PDF, OCR-preprocessing, tests, and VS Code support.

## Features

- **Accounts:** registration, login/logout, hashed passwords, and per-user expense isolation.
- **Receipt OCR:** upload JPG/JPEG, PNG, WEBP, TIFF, BMP, or PDF receipts. Images are resized, deskew-friendly contrast normalized, denoised/thresholded, and scanned with multiple Tesseract layout modes. PDFs are rasterized before OCR.
- **Review before save:** OCR proposes merchant, amount, date, and category; the user can correct every field before saving. Raw OCR text is available for troubleshooting.
- **Expense management:** manual entry without a receipt, searchable/filterable expense list, edit/delete, receipt viewing, and CSV export.
- **Dashboard:** total and current-month spending, recent expenses, category breakdown, and a six-month spending trend.
- **Analytics:** 12-month spending chart, category chart, top merchants, and all-time total.
- **Budgets:** set a monthly budget per category, track actual spending against the limit, and see remaining/over-budget amounts.
- **UI:** responsive layout for desktop/mobile, light/dark theme toggle, navbar/sidebar, flash messages, and empty states.
- **Developer support:** VS Code launch/tasks, Windows setup scripts, pytest tests, and a GitHub Actions workflow.

> OCR is best-effort. Receipt layouts, blurry photos, handwriting, unusual currencies, and low contrast can affect results. Always verify the suggested amount/date/vendor before saving. OCR currently uses Tesseract; it does not use a cloud AI service.

## Requirements

- Python 3.10+ (Python 3.11 or 3.12 recommended)
- Tesseract OCR installed separately on your computer
- Packages in `requirements.txt`

### Install Tesseract on Windows

1. Install the Tesseract OCR engine from the official UB Mannheim Windows builds: <https://github.com/UB-Mannheim/tesseract/wiki>.
2. During installation, note the folder containing `tesseract.exe` (commonly `C:\Program Files\Tesseract-OCR`).
3. Add that folder to your Windows `PATH`, then close and reopen VS Code/Command Prompt.
4. Verify by running `tesseract --version` in the VS Code terminal.

On macOS, install with `brew install tesseract`. On Ubuntu/Debian, install with `sudo apt-get install tesseract-ocr`.

If Windows cannot find Tesseract, set `TESSERACT_CMD` in your local `.env` file to the full path of `tesseract.exe` (for example `TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe`). Only use that example if it matches the actual install path on your computer.

## Run in VS Code (Windows)

1. Extract the project ZIP into a normal folder, such as `Documents\ExpenseFlow-Pro`.
2. Open VS Code → **File → Open Folder…** → select the extracted `expenseflow_pro` folder.
3. Open **Terminal → New Terminal**. Make sure the terminal is in the folder that contains `requirements.txt`.
4. Run the setup script once:

   ```bat
   setup_windows.bat
   ```

5. Install Tesseract using the steps above, then start the app:

   ```bat
   run_windows.bat
   ```

6. Open <http://127.0.0.1:5000> in your browser and create an account.

### Manual setup (Windows)

```bat
py -m venv .venv
.venv\Scripts\activate
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py run.py
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests cover registration/dashboard rendering, manual entry, analytics/CSV export, budgets, login protection, and receipt parsing. GitHub Actions runs compile checks and tests on pushes and pull requests.

## Publish this project to your GitHub account

This ZIP is a source project; it does not contain a `.git` directory or upload anything automatically.

1. Sign in to GitHub and create a **new empty repository** under your account. Do not add a README/license on GitHub if you want to push this README unchanged.
2. Open the extracted project folder in VS Code.
3. Open **Source Control** in the left sidebar and choose **Initialize Repository**.
4. Review the file list. The `.gitignore` excludes your local database, uploaded receipts, virtual environment, and `.env` secrets.
5. Enter a commit message such as `Initial ExpenseFlow Pro version`, then choose **Commit**.
6. Choose **Publish to GitHub** (or add the remote URL shown by GitHub and push from the terminal). Select the repository you just created.
7. Never commit real receipt photos, your `instance/expenseflow.db`, `.env`, passwords, or API/secret keys.

Alternatively, after creating an empty GitHub repository, use the terminal commands GitHub displays for an existing local repository. Ensure Git is installed first (`git --version`).

## Project structure

```text
expenseflow_pro/
├── app/
│   ├── __init__.py          # Flask app factory, database, login, CSRF setup
│   ├── auth.py              # Register/login/logout
│   ├── main.py              # Dashboard, receipts, expenses, analytics, budgets, CSV
│   ├── models.py            # User, Expense, Budget database models
│   ├── ocr.py               # Image/PDF preprocessing, Tesseract OCR, field parsing
│   ├── static/style.css     # Responsive theme and component styles
│   ├── templates/           # Jinja HTML templates
│   └── uploads/.gitkeep     # Empty upload folder placeholder
├── tests/test_app.py
├── .github/workflows/tests.yml
├── .vscode/                 # VS Code launch configuration and tasks
├── requirements.txt
├── requirements-dev.txt
├── setup_windows.bat
├── run_windows.bat
└── run.py
```

## Data and security notes

- SQLite data is stored under Flask's local `instance/` folder; uploaded receipts are stored in `app/uploads/`.
- Uploaded files use randomized names, upload size and extension limits, and per-user ownership checks for saved receipts.
- CSRF protection is enabled for form submissions.
- The default secret key is for local development only. Before deployment, set a long random `SECRET_KEY` environment variable and use HTTPS, secure cookies, a production WSGI server, backups, and rate limiting.
- This is a learning/development application, not a financial or accounting system. Keep backups and verify extracted information.

## License

MIT — see `LICENSE`.


### Budget alerts

ExpenseFlow displays a gentle warning when a category reaches 80% of its monthly budget and a clear exceeded-budget alert at 100% or more. Alerts appear on the dashboard and Budgets page, and saving a receipt/manual expense can trigger a flash warning. Suggestions are tailored to the spending category.
