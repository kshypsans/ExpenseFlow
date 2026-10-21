from dotenv import load_dotenv
from app import create_app

# Load local .env values for development. Never commit real secrets.
load_dotenv()
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
