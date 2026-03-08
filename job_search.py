"""Job posting search and skill aggregation.

Fetches real job postings via JSearch API on RapidAPI and aggregates
the required skills across postings. If the AI isn't available uses the labor data as a fallback
"""

import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)


def fetch_and_aggregate_skills(target_role, rapidapi_key=''):
    """
    Get market skill requirements for a target role.

    Will revert to fallback skills if API is unavailable.
    """
    if rapidapi_key:
        try:
            postings = _fetch_jsearch_postings(target_role, rapidapi_key)
            if postings:
                skills = _aggregate_skills_from_postings(postings)
                return {
                    'skills': skills,
                    'source': 'Live job postings (LinkedIn, Indeed, Glassdoor & more)',
                    'postings_count': len(postings),
                }
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (401, 403):
                logger.warning("Invalid or expired RapidAPI key — falling back to synthetic data")
            else:
                logger.warning("JSearch API call failed, falling back to synthetic data", exc_info=True)
        except Exception:
            logger.warning("JSearch API call failed, falling back to synthetic data", exc_info=True)

    return _fetch_synthetic_skills(target_role)


def _fetch_jsearch_postings(target_role, rapidapi_key, num_pages=5):
    """
    Query the JSearch API for active job postings matching a role.
    """

    url = 'https://jsearch.p.rapidapi.com/search'

    headers = {
        'X-RapidAPI-Key': rapidapi_key,
        'X-RapidAPI-Host': 'jsearch.p.rapidapi.com',
    }

    params = {
        'query': target_role,
        'num_pages': str(num_pages),
        'page': '1',
    }

    response = requests.get(url, headers=headers, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    return data.get('data', [])


def _aggregate_skills_from_postings(postings):
    """
    Count how often each skill appears across a set of job postings
    using each posting's job description and qualifications for those
    keywords.

    """
    total = len(postings)
    if total == 0:
        return []

    skill_counts = {}

    for posting in postings:
        # combine all the text fields that might mention skills
        text_parts = [
            posting.get('job_description', ''),
            posting.get('job_highlights', {}).get('Qualifications', [''])[0]
            if isinstance(posting.get('job_highlights', {}).get('Qualifications'), list)
            else '',
            posting.get('job_required_skills', ''),
        ]
        combined_text = ' '.join(str(p) for p in text_parts).lower()

        # track which skills that appear in this specific posting
        found_in_posting = set()

        for skill, patterns in _SKILL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined_text):
                    found_in_posting.add(skill)
                    break

        for skill in found_in_posting:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

    # creating the final list based on how often each skill appears
    skills = []
    for skill, count in sorted(skill_counts.items(), key=lambda x: x[1], reverse=True):
        skills.append({
            'skill': skill,
            'frequency': round(count / total * 100),
            'count': count,
            'total': total,
        })

    return skills


def _fetch_synthetic_skills(target_role):
    """
    Load skill requirements from the bundled data. It uses fuzzy matching since the user can essentially type whatever
    title they want and the data might not have the specific role title.
    """
    
    data_path = os.path.join(os.path.dirname(__file__), 'data', 'skills_database.json')
    try:
        with open(data_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'skills': [], 'source': 'none', 'postings_count': 0}

    roles = data.get('roles', {})
    if not roles:
        return {'skills': [], 'source': 'none', 'postings_count': 0}

    # trying to match the words exactly first before doing the fuzzy matching
    role_data = roles.get(target_role)

    if not role_data:
        best_match, best_score = _find_closest_role(target_role, roles.keys())
        if best_score > 0:
            role_data = roles[best_match]

    if not role_data:
        return {'skills': [], 'source': 'O*NET (no matching role)', 'postings_count': 0}

    # build a skill list that mimics what we'd get from real postings
    skills = []

    required = role_data.get('required_skills', [])
    for i, skill in enumerate(required):
        
        # required skills get higher simulated frequency
        freq = max(95 - (i * 5), 60)
        
        skills.append({
            'skill': skill,
            'frequency': freq,
            'count': freq,
            'total': 100,
        })

    preferred = role_data.get('preferred_skills', [])
    for i, skill in enumerate(preferred):
        freq = max(50 - (i * 5), 20)
        skills.append({
            'skill': skill,
            'frequency': freq,
            'count': freq,
            'total': 100,
        })

    return {
        'skills': skills,
        'source': 'O*NET occupational data',
        'postings_count': len(required) + len(preferred),
    }


def _find_closest_role(target, known_roles):
    """
    Find the best matching role name using word overlap.
    """
    
    target_words = set(target.lower().split())
    best_match = None
    best_score = 0

    for role in known_roles:
        role_words = set(role.lower().split())
        
        # count shared words relative to total unique words
        overlap = len(target_words & role_words)
        total = len(target_words | role_words)
        score = overlap / total if total > 0 else 0

        if score > best_score:
            best_score = score
            best_match = role

    return best_match, best_score


# I used regex patterns for trying to extract the skills from job posting text.
# but I also needed to use boundaries to avoid having like false positives. I do understand that this is somewhat hardcoded, however
# if I have more time I will refactor this code later on

_SKILL_PATTERNS = {
    'Python': [r'\bpython\b'],
    'JavaScript': [r'\bjavascript\b', r'\bjs\b'],
    'TypeScript': [r'\btypescript\b'],
    'Java': [r'\bjava\b(?!script)'],
    'C#': [r'\bc#\b', r'\bcsharp\b'],
    'C++': [r'\bc\+\+\b'],
    'Go': [r'\bgolang\b', r'\bgo\b(?:\s+(?:lang|programming))'],
    'Rust': [r'\brust\b'],
    'Ruby': [r'\bruby\b'],
    'PHP': [r'\bphp\b'],
    'Swift': [r'\bswift\b'],
    'Kotlin': [r'\bkotlin\b'],
    'SQL': [r'\bsql\b'],
    'R': [r'\br\b(?:\s+(?:programming|language|studio))'],
    'React': [r'\breact\b', r'\breactjs\b', r'\breact\.js\b'],
    'Angular': [r'\bangular\b'],
    'Vue.js': [r'\bvue\b', r'\bvuejs\b', r'\bvue\.js\b'],
    'Node.js': [r'\bnode\.?js\b', r'\bnode\b'],
    'Django': [r'\bdjango\b'],
    'Flask': [r'\bflask\b'],
    'Spring Boot': [r'\bspring\s*boot\b', r'\bspring\s+framework\b'],
    'AWS': [r'\baws\b', r'\bamazon\s+web\s+services\b'],
    'Azure': [r'\bazure\b', r'\bmicrosoft\s+azure\b'],
    'GCP': [r'\bgcp\b', r'\bgoogle\s+cloud\b'],
    'Docker': [r'\bdocker\b'],
    'Kubernetes': [r'\bkubernetes\b', r'\bk8s\b'],
    'Terraform': [r'\bterraform\b'],
    'CI/CD': [r'\bci/?cd\b', r'\bcontinuous\s+(?:integration|deployment|delivery)\b'],
    'Jenkins': [r'\bjenkins\b'],
    'GitHub Actions': [r'\bgithub\s+actions\b'],
    'Git': [r'\bgit\b(?!hub)'],
    'Linux': [r'\blinux\b'],
    'PostgreSQL': [r'\bpostgresql\b', r'\bpostgres\b'],
    'MySQL': [r'\bmysql\b'],
    'MongoDB': [r'\bmongodb\b', r'\bmongo\b'],
    'Redis': [r'\bredis\b'],
    'Elasticsearch': [r'\belasticsearch\b', r'\belastic\s+search\b'],
    'Machine Learning': [r'\bmachine\s+learning\b', r'\bml\b'],
    'Deep Learning': [r'\bdeep\s+learning\b'],
    'TensorFlow': [r'\btensorflow\b'],
    'PyTorch': [r'\bpytorch\b'],
    'NLP': [r'\bnlp\b', r'\bnatural\s+language\s+processing\b'],
    'REST APIs': [r'\brest\s*api\b', r'\brestful\b'],
    'GraphQL': [r'\bgraphql\b'],
    'Agile/Scrum': [r'\bagile\b', r'\bscrum\b'],
    'Network Security': [r'\bnetwork\s+security\b'],
    'Firewalls': [r'\bfirewall\b'],
    'IAM': [r'\biam\b', r'\bidentity\s+(?:and\s+)?access\s+management\b'],
    'Incident Response': [r'\bincident\s+response\b'],
    'Penetration Testing': [r'\bpenetration\s+testing\b', r'\bpentest\b'],
    'Compliance': [r'\bcompliance\b'],
    'Encryption': [r'\bencryption\b', r'\bcryptography\b'],
    'Tableau': [r'\btableau\b'],
    'Power BI': [r'\bpower\s*bi\b'],
    'Excel': [r'\bexcel\b'],
    'Figma': [r'\bfigma\b'],
    'SEO': [r'\bseo\b'],
    'Google Analytics': [r'\bgoogle\s+analytics\b'],
    'Jira': [r'\bjira\b'],
    'HTML': [r'\bhtml\b'],
    'CSS': [r'\bcss\b'],
    'Tailwind CSS': [r'\btailwind\b'],
    'Pandas': [r'\bpandas\b'],
    'NumPy': [r'\bnumpy\b'],
    'Apache Spark': [r'\bspark\b', r'\bapache\s+spark\b'],
    'Kafka': [r'\bkafka\b'],
    'Snowflake': [r'\bsnowflake\b'],
    'Data Warehousing': [r'\bdata\s+warehouse?\b', r'\bdata\s+warehousing\b'],
    'Serverless': [r'\bserverless\b', r'\blambda\b'],
    'Zero Trust': [r'\bzero\s+trust\b'],
}