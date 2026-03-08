# Design Document For Skill Bridge Career Navigator

## Design

I decided to have this application follow a layered architecture in order to ensure there was a separation of concerns:

- **`app.py`**: Route definitions, request validation, and template rendering
- **`resume_parser.py`**: Does the resume text extraction (PDF, DOCX, TXT) and skill identification
- **`ai_engine.py`** : Gap analysis and roadmap generation using the OpenAI API is done in this file
- **`job_search.py`** : Job market data fetching with the JSearch API and skill aggregation is done here
- **`models.py`**: The database models and data access via SQLAlchemy ORM
- **`data/`** : The JSON files for synthetic fallback data, skill aliases, and curated learning resources are in this directory

As for the fallback pattern, every external dependency (OpenAI, JSearch API) has a local data counterpart. If the AI is unavailable, the skill extraction falls back to keyword matching. If the JSearch API is unavailable, the market data falls back to a bundled skills database. I did this to ensures the app produces meaningful results even with zero API keys configured.

## User Flow

1. **Onboarding**: The user fills out a form with their name, email, persona (e.g., recent grad, career switcher), target role, and either uploads a resume file or pastes resume text.
2. **Skill Extraction**: The app extracts text from the file (if uploaded) and then saves the profile, and redirects to a loading page. The loading page then calls an API endpoint that extracts skills from the resume text using AI (or keyword matching as a fallback).
3. **Profile View**: The user sees their profile with extracted skills displayed.
4. **Gap Analysis**: The dashboard compares the user's skills against real job market data for their target role. It shows matched skills, missing skills, and a strength score.
5. **Learning Roadmap**: A personalized roadmap is generated with prioritized skills to learn and curated resources (free and paid) for each skill.
6. **Edit & Refresh**: The user can update their skills or target role at any time. Changing either however, will invalidate the cached analysis so it regenerates on the next dashboard visit.

## Design Choices

- **Flask** — I chose Flask because its lightweight and I've had some experience working with it already to make other prototypes and MVPs so I thought it would be a great choice for that purpose.
- **SQLite** — Similarly I chose SQLite for the same purpose as Flask, its simple and lightweight and works well for a demonstration MVP.
- **Text-first extraction** — I wanted to try and minimize the amount of tokens I was using when working with ChatGPT so instead of passing in the file, I thought it would be better to first extract the text from the file or the text input and then pass that text into the GPT model.
- **Fallback pattern** — Since I am utilizing both the GPT model and the JSearch API I believed it was best to have fallbacks in case both or either don't work. While they might have more general results as my synthetic data might not cover every skill or every job title, I thought it was best to have that to at least produce some result even if it was a little more general.
- **Async skill extraction** — The onboarding form saves the profile immediately and shows a loading page while skills are extracted in the background. This keeps the user experience responsive even when the AI call is slow.

## Tech Stack

### Programming Languages

- **Python 3.11** — Backend logic, API integrations, and data processing
- **HTML/CSS/JavaScript** — Frontend templates and interactivity

### Frameworks

- **Flask 3.1** — Web framework for routing, request handling, and template rendering
- **Flask-SQLAlchemy 3.1** — ORM layer for database models and queries
- **Bootstrap 5** — Frontend component library for responsive UI

### Libraries

- **OpenAI SDK** (`openai >= 2.26.0`) — Client for the OpenAI Responses API
- **PyPDF** (`pypdf 6.5`) — PDF text extraction from uploaded resumes
- **python-docx** (`1.2.0`) — DOCX text extraction from uploaded resumes
- **Requests** (`2.32.5`) — HTTP client for the JSearch API
- **python-dotenv** (`1.2.2`) — Environment variable management from `.env` files
- **pytest** (`9.0.2`) — Test framework

### AI Models

- **GPT-5-mini** (`gpt-5-mini`) — Used for three tasks:
  1. Skill extraction from resume text (`resume_parser.py`)
  2. Gap analysis between user skills and market requirements (`ai_engine.py`)
  3. Personalized learning roadmap generation (`ai_engine.py`)

### AI Usage (coding assistance)

I used Claude Code as my primary coding assistant. On the backend side, I mainly had it provide me syntactical help when working with particular libraries and there were some times where I needed Claude to step in for some minor tasks or to help me understand some libraries and clear up my confusion. Most of the backend code was done manually by myself though. The heavier lifting from Claude however came on the frontend side of things, as to not waste too much time on that aspect. I utilized particular skills that Claude Code has access to like Anthropic's `frontend-design` skill and other unofficial skills like the `UI/UX Design Pro` skill. That said, I did also make sure to verify that its output was correct before utilizing its suggestions.

## Future Enhancements

- **Authentication** — User registration and login with password hashing (bcrypt + salt) so that each user can only view and manage their own profile
- **UUIDs** — Replace sequential integer IDs with UUIDs to make profile endpoints harder to enumerate
- **Persona-specific features** — Add unique analysis sections for each persona type (currently only the career switcher has a distinct "transferable skills" section)
- **Expanded skill detection** — Move the hardcoded regex skill patterns to a configurable data file or use AI-based skill extraction from job postings
- **Production database** — Migrate from SQLite to PostgreSQL for concurrent user support