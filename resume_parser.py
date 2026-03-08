"""Resume parsing and skill extraction.

Handles three input formats (PDF, DOCX, plain text) and extracts skills
using either OpenAI or a keyword-based fallback.
"""

import io
import json
import logging
import re

from pypdf import PdfReader
from docx import Document

logger = logging.getLogger(__name__)


# Skills to look for during keyword-based fallback extraction.
# I grouped it loosely by domain so it's easier to maintain if needed later on.
KNOWN_SKILLS = [
    # programming languages
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "C", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Bash", "PowerShell",
    "Solidity", "Assembly", "Perl", "Lua", "Dart", "Elixir", "Haskell",

    # web & frontend
    "React", "Angular", "Vue.js", "Next.js", "HTML", "CSS", "Tailwind CSS",
    "Bootstrap", "Svelte", "jQuery", "Webpack", "REST APIs", "GraphQL",
    "Node.js", "Express", "Django", "Flask", "FastAPI", "Spring Boot",
    "Ruby on Rails", "ASP.NET", "Laravel",

    # data & ml
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Scikit-learn",
    "Pandas", "NumPy", "Jupyter", "NLP", "Computer Vision", "Statistics",
    "Data Visualization", "Tableau", "Power BI", "Looker", "Apache Spark",
    "Kafka", "Airflow", "ETL", "Data Warehousing", "Snowflake", "dbt",
    "A/B Testing", "Feature Engineering",

    # cloud & devOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible",
    "CI/CD", "Jenkins", "GitHub Actions", "ArgoCD", "Helm", "Linux",
    "Networking", "DNS", "TCP/IP", "Load Balancing", "Serverless",
    "Infrastructure as Code", "Monitoring", "Prometheus", "Grafana",

    # security
    "Network Security", "SIEM", "Splunk", "Wireshark", "Firewalls", "IAM",
    "Incident Response", "Penetration Testing", "Vulnerability Management",
    "Compliance", "Risk Assessment", "OWASP", "Encryption", "VPN",
    "IDS/IPS", "Malware Analysis", "Threat Intelligence", "Security Scanning",
    "SAST", "DAST", "Forensics", "Security Frameworks", "NIST", "ISO 27001",
    "Palo Alto Networks", "Zero Trust",

    # tools & practices
    "Git", "Jira", "Agile/Scrum", "Scrum", "Kanban", "Confluence",
    "Figma", "Adobe Creative Suite", "Photoshop", "Illustrator",
    "Testing", "Selenium", "Cypress", "Playwright", "pytest",

    # business & marketing
    "SEO", "Google Analytics", "Content Strategy", "Social Media Marketing",
    "PPC/SEM", "Email Marketing", "Marketing Automation", "CRM", "Salesforce",
    "HubSpot", "Copywriting", "Financial Modeling", "Excel", "ERP Systems",
    "Project Planning", "Stakeholder Management", "Technical Writing",
    "User Research", "Wireframing", "Prototyping", "Design Systems",
    "Data Analysis", "Reporting", "Business Intelligence",
    "Product Strategy", "Roadmap Planning", "Requirements Gathering",
]

# sometimes people use aliases so I decided to map them
SKILL_ALIASES = {
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "k8s": "Kubernetes",
    "tf": "Terraform",
    "react.js": "React",
    "reactjs": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "postgres": "PostgreSQL",
    "mongo": "MongoDB",
    "aws ec2": "AWS",
    "aws s3": "AWS",
    "aws lambda": "AWS",
    "amazon web services": "AWS",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "microsoft azure": "Azure",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "ml": "Machine Learning",
    "ai": "Machine Learning",
    "nlp": "NLP",
    "dl": "Deep Learning",
    "scikit learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "html5": "HTML",
    "css3": "CSS",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "restful": "REST APIs",
    "graphql": "GraphQL"
}


def extract_text_from_file(file):
    """Pull plain text out of an uploaded file.

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
    """Extract skills from resume text using the AI but if not then it just falls back to the keyword matching.

    Returns a dict
    """
    # Try extracting it with the AI first
    if openai_key:
        try:
            return _extract_skills_with_ai(resume_text, openai_key)
        except Exception:
            logger.warning("AI skill extraction failed, falling back to keyword matching", exc_info=True)

    return _extract_skills_with_keywords(resume_text)


def _extract_skills_with_ai(resume_text, openai_key):
    """
    Use OpenAI extract skills from resume text.
    """
    from openai import OpenAI

    client = OpenAI(api_key=openai_key)

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=(
            "You are a resume skills extractor. Extract all technical skills, "
            "tools, frameworks, certifications, and technologies from the resume. "
            "Also estimate years of professional experience. "
            "Return ONLY valid JSON with this exact structure: "
            '{"skills": ["skill1", "skill2"], "experience_years": 2}'
        ),
        input=f"Extract skills from this resume:\n\n{resume_text[:3000]}",
        max_output_tokens=2000,
    )

    content = response.output_text.strip()

    # Handle cases where the AI wraps the JSON in markdown code blocks
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

    # Check aliases first
    for alias, canonical in SKILL_ALIASES.items():
        if alias in text_lower:
            found_skills.add(canonical)

    # Check each known skill as a whole-word match
    for skill in KNOWN_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, resume_text, re.IGNORECASE):
            found_skills.add(skill)

    # Try to guess years of experience from common resume patterns
    experience_years = _estimate_experience(resume_text)

    return {
        'skills': sorted(found_skills, key=str.lower),
        'experience_years': experience_years,
        'method': 'keyword_matching',
    }


def _estimate_experience(resume_text):
    """Try to guess years of experience from resume text.

    if nothing is found then just return 0.
    """
    patterns = [
        r'(\d+)\+?\s*years?\s+of\s+experience',
        r'(\d+)\+?\s*years?\s+(?:in|of|working)',
        r'experience[:\s]+(\d+)\+?\s*years?',
    ]

    max_years = 0
    for pattern in patterns:
        matches = re.findall(pattern, resume_text, re.IGNORECASE)
        for match in matches:
            years = int(match)
            
            # did this just as kind of a sanity check
            if 0 < years < 50:
                max_years = max(max_years, years)

    return max_years