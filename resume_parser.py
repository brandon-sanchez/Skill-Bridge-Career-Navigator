"""Resume parsing and skill extraction.

Handles three input formats (pdf, docx, and plain text) and extracts skills
using either OpenAI or a keyword-based fallback.
"""

import io
import json
import logging
import os
import re

from pypdf import PdfReader
from docx import Document
from openai import AuthenticationError, RateLimitError, OpenAI

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def _load_known_skills():
    """
    Build the known skills list from skills_database.json.
    """
    path = os.path.join(DATA_DIR, 'skills_database.json')
    try:
        with open(path, 'r') as f:
            roles = json.load(f).get('roles', {})
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    skills = set()
    for role_data in roles.values():
        skills.update(role_data.get('required_skills', []))
        skills.update(role_data.get('preferred_skills', []))
    return sorted(skills)


def _load_skill_aliases():
    """Load abbreviation mappings from skill_aliases.json."""
    path = os.path.join(DATA_DIR, 'skill_aliases.json')
    try:
        with open(path, 'r') as f:
            return json.load(f).get('aliases', {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# load once at import time so don't read files on every request
KNOWN_SKILLS = _load_known_skills()
SKILL_ALIASES = _load_skill_aliases()


def extract_text_from_file(file):
    """
    Pull the plain text out of an uploaded file

    Returns the extracted text as a string, or else it will raise an error if the
    format isn't supported.
    """
    filename = file.filename.lower()

    # For pdf
    if filename.endswith('.pdf'):
        reader = PdfReader(io.BytesIO(file.read()))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return '\n'.join(text_parts)

    # For docx
    elif filename.endswith('.docx'):
        doc = Document(io.BytesIO(file.read()))
        return '\n'.join(paragraph.text for paragraph in doc.paragraphs)

    # For txt
    elif filename.endswith('.txt'):
        return file.read().decode('utf-8', errors='ignore')

    else:
        raise ValueError(f'Unsupported file format: {filename}. Please use PDF, DOCX, or TXT.')


def extract_skills(resume_text, openai_key=''):
    """
    Extract skills from resume text using the AI but if not then it just falls back to the keyword matching.

    Returns a dict
    """

    # try extracting it with the AI first
    if openai_key:
        try:
            return _extract_skills_with_ai(resume_text, openai_key)
        except AuthenticationError:
            logger.warning("Invalid OpenAI API key — falling back to keyword matching")
        except RateLimitError:
            logger.warning("OpenAI rate limit hit — falling back to keyword matching")
        except Exception:
            logger.warning("AI skill extraction failed, falling back to keyword matching", exc_info=True)

    return _extract_skills_with_keywords(resume_text)


def _extract_skills_with_ai(resume_text, openai_key):
    """
    Use OpenAI extract skills from resume text.
    """

    client = OpenAI(api_key=openai_key)

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=(
            "You are a resume skills extractor. Extract all technical skills, "
            "tools, frameworks, certifications, and technologies from the resume. "
            "Return ONLY valid JSON with this exact structure: "
            '{"skills": ["skill1", "skill2"]}'
        ),
        input=f"Extract skills from this resume:\n\n{resume_text[:3000]}",
        max_output_tokens=2000,
    )

    content = response.output_text.strip()

    # handle cases where the AI wraps the JSON in markdown code blocks (was having trouble with this so added
    # this for debugging)
    if content.startswith('```'):
        content = content.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

    result = json.loads(content)
    result['method'] = 'ai'
    return result


def _extract_skills_with_keywords(resume_text):
    """
    Scan the resume for known skill keywords. Fallback for when AI doesn't work
    """
    text_lower = resume_text.lower()
    found_skills = set()

    # check aliases first
    for alias, canonical in SKILL_ALIASES.items():
        if alias in text_lower:
            found_skills.add(canonical)

    # check each known skill as a whole-word match
    for skill in KNOWN_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, resume_text, re.IGNORECASE):
            found_skills.add(skill)

    return {
        'skills': sorted(found_skills, key=str.lower),
        'method': 'keyword_matching',
    }