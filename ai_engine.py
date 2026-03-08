"""AI-powered gap analysis and roadmap generation.

This module is for the roadmap generation based on the analysis. It compares a user's skills against
what most job descriptions want and then generates a personalized learning roadmap.
"""

import json
import logging
import os

from job_search import fetch_and_aggregate_skills
from openai import OpenAI

logger = logging.getLogger(__name__)

# persona descriptions
PERSONA_CONTEXT = {
    'recent_grad': 'a recent graduate looking to break into the field',
    'career_switcher': 'someone switching careers — emphasize transferable skills',
    'upskilling': 'a professional looking to level up in their current field',
    'mentor': 'a mentor evaluating a mentee\'s readiness for this role',
}


def analyze_gaps(user_skills, target_role, persona, openai_key='', rapidapi_key=''):
    """
    Compare the user's skills against market demand for their target role.
    Returns a dict with matched_skills, missing_skills, strength_score, summary, etc.
    """
    
    # get what most job descriptions wants for this role
    market_data = fetch_and_aggregate_skills(target_role, rapidapi_key)
    market_skills = market_data.get('skills', [])
    data_source = market_data.get('source', 'unknown')
    postings_analyzed = market_data.get('postings_count', 0)

    # try ai analysis first if not then use fallback
    if openai_key:
        try:
            return _analyze_gaps_with_ai(
                user_skills, target_role, persona, market_skills,
                data_source, postings_analyzed, openai_key
            )
        except Exception:
            logger.warning("AI gap analysis failed, using fallback to analyize the gaps", exc_info=True)

    return _analyze_gaps_fallback(
        user_skills, target_role, persona, market_skills,
        data_source, postings_analyzed
    )


def generate_roadmap(missing_skills, target_role, persona, openai_key=''):
    """
    Build a phased learning plan for the user's skill gaps.

    Returns a dict with phases, each containing free and paid resource suggestions.
    """
    if openai_key:
        try:
            return _generate_roadmap_with_ai(missing_skills, target_role, persona, openai_key)
        except Exception:
            logger.warning("AI roadmap generation failed, falling back to curated resources", exc_info=True)

    return _generate_roadmap_fallback(missing_skills, target_role, persona)

def _analyze_gaps_with_ai(user_skills, target_role, persona, market_skills,
                          data_source, postings_analyzed, openai_key):
    """Use OpenAI to produce a nuanced gap analysis with persona-specific framing."""

    client = OpenAI(api_key=openai_key)

    # create a readable summary of what the market wants
    market_summary = '\n'.join(
        f"- {s['skill']}: required in {s['frequency']}% of postings"
        for s in market_skills[:20]
    ) if market_skills else f"Common skills for {target_role} role"

    transferable_line = '  "transferable_skills": ["skill from their background that applies in a different context"],' if persona == 'career_switcher' else '  "transferable_skills": [],'

    prompt = f"""You are a career advisor analyzing a skills gap. Be specific and actionable.

    User's current skills: {', '.join(user_skills)}
    Target role: {target_role}
    User context: {PERSONA_CONTEXT.get(persona, 'a job seeker')}
    
    Market demand (from {postings_analyzed} job postings via {data_source}):
    {market_summary}
    
    Return ONLY valid JSON with this structure:
    {{
      "matched_skills": [{{"skill": "Python", "strength": "strong", "note": "78%"}}],
      "missing_skills": [{{"skill": "Terraform", "priority": "high", "note": "78%"}}],
    {transferable_line}
      "strength_score": 45,
      "summary": "2-3 sentence personalized assessment",
      "data_source": "{data_source}",
      "postings_analyzed": {postings_analyzed},
      "method": "ai"
    }}
    
    Prioritize missing_skills by how frequently they appear in job postings.
    The "note" field must be ONLY the percentage number followed by % (e.g. "78%"). No descriptions or extra text.
    Be encouraging but honest in the summary."""

    response = client.responses.create(
        model="gpt-5-mini",
        instructions="You are a career skills advisor. Return only valid JSON.",
        input=prompt,
        max_output_tokens=4000,
    )

    content = response.output_text
    if not content:
        raise ValueError("Empty response from AI model")
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

    return json.loads(content)


def _generate_roadmap_with_ai(missing_skills, target_role, persona, openai_key):
    """Ask OpenAI to build a phased learning plan with real course recommendations."""

    client = OpenAI(api_key=openai_key)

    skills_text = ', '.join(
        s.get('skill', s) if isinstance(s, dict) else s
        for s in missing_skills[:15]
    )

    prompt = f"""You are a learning path designer. Create a phased roadmap for someone targeting
    a {target_role} role. They are {PERSONA_CONTEXT.get(persona, 'a job seeker')}.

    Skills they need to learn (by priority): {skills_text}
    
    For EACH skill, suggest REAL, specific courses and resources that exist. Include a MIX of:
    - Video courses (YouTube, Udemy, Coursera, LinkedIn Learning, DeepLearningAI)
    - Articles and tutorials (freeCodeCamp, Medium, official docs, Dev.to)
    - Hands-on projects or labs where applicable
    Separate free and paid options. Include estimated hours.
    Organize phases by time to complete (shortest first). Group related skills together.
    
    FORMATTING RULES:
    - Phase names must be short: "Phase 1: Foundations", "Phase 2: MLOps", etc. No long descriptions in titles.
    - Resource titles must be concise: just the course/article name, no descriptions or parenthetical notes. Max ~50 characters.
    
    RESOURCE RULES:
    - Maximum 5 free resources and 3 paid resources per phase. Choose only the most impactful ones for job readiness.
    - Use a mix of media types (videos, articles, projects) covering DIFFERENT subtopics.
    - Do NOT repeat the same subtopic within the same media type.
    - Include at least one hands-on project or exercise per phase so learners can apply what they learn.
    - Focus on resources that build skills employers actually test for in interviews and on the job.
    
    Each resource MUST include a "type" field: "video", "article", "course", or "project".
    
    Return ONLY valid JSON:
    {{
      "phases": [
        {{
          "phase_name": "Phase 1: Foundations",
          "duration": "2-3 weeks",
          "skills": ["skill1", "skill2"],
          "free_resources": [
            {{"title": "Specific Course/Article Name", "platform": "YouTube/freeCodeCamp/Coursera", "url": "https://...", "est_hours": 5, "type": "video"}}
          ],
          "paid_resources": [
            {{"title": "Specific Course Name", "platform": "Udemy/Coursera/LinkedIn Learning", "url": "https://...", "est_hours": 20, "price_range": "$10-50", "type": "course"}}
          ]
        }}
      ],
      "total_estimated_time": "3-6 months",
      "certifications_recommended": [{{"name": "Cert Name", "relevance": "high", "cost": "$150"}}],
      "method": "ai"
    }}
    
    IMPORTANT: Use REAL URLs that actually exist. If unsure about a URL, use a platform
    search URL instead (e.g., https://www.udemy.com/courses/search/?q=terraform).
    Keep it practical — 3-5 phases maximum."""

    response = client.responses.create(
        model="gpt-5-mini",
        instructions="You are a learning path designer. Provide comprehensive, in-depth resources — enough for someone to become job-ready. Be thorough, not minimal. Return only valid JSON.",
        input=prompt,
        max_output_tokens=16000,
    )

    content = response.output_text
    if not content:
        raise ValueError("Empty response from AI model")
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

    result = json.loads(content)

    # sort resources by estimated hours and cap at 5 free / 3 paid
    for phase in result.get('phases', []):
        phase.get('free_resources', []).sort(key=lambda r: r.get('est_hours', 0))
        phase.get('paid_resources', []).sort(key=lambda r: r.get('est_hours', 0))
        phase['free_resources'] = phase.get('free_resources', [])[:5]
        phase['paid_resources'] = phase.get('paid_resources', [])[:3]

    return result


def _analyze_gaps_fallback(user_skills, target_role, persona, market_skills,
                           data_source, postings_analyzed):
    """Compares user skills against market requirements by using matching.
    """
    user_skills_lower = {s.lower() for s in user_skills}

    matched = []
    missing = []

    for market_skill in market_skills:
        skill_name = market_skill.get('skill', market_skill) if isinstance(market_skill, dict) else market_skill
        frequency = market_skill.get('frequency', 0) if isinstance(market_skill, dict) else 0

        if skill_name.lower() in user_skills_lower:
            matched.append({
                'skill': skill_name,
                'strength': 'strong',
                'note': f'{frequency}%' if frequency else '',
            })
        else:
            priority = 'high' if frequency > 60 else 'medium' if frequency > 30 else 'low'
            missing.append({
                'skill': skill_name,
                'priority': priority,
                'note': f'{frequency}%' if frequency else '',
            })

    total = len(matched) + len(missing)
    score = round((len(matched) / total * 100)) if total > 0 else 0

    # summary
    summaries = {
        'recent_grad': f"You match {len(matched)} out of {total} skills commonly required for {target_role}. Focus on the high-priority gaps to become competitive.",
        'career_switcher': f"You bring {len(matched)} relevant skills to the {target_role} role. Your existing experience gives you a foundation — the missing skills are learnable.",
        'upskilling': f"You already have {len(matched)} of the {total} key skills. Filling the remaining gaps will strengthen your profile significantly.",
        'mentor': f"This mentee has {len(matched)} of {total} target skills for {target_role}. The learning roadmap below can guide their development.",
    }

    return {
        'matched_skills': matched,
        'missing_skills': missing,
        'transferable_skills': [],
        'strength_score': score,
        'summary': summaries.get(persona, f"You match {len(matched)} of {total} required skills."),
        'data_source': data_source,
        'postings_analyzed': postings_analyzed,
        'method': 'fallback',
    }


def _load_skill_topic_map():
    """Built a reverse index from skill name to topic category using skills_database.json.
    """
    onet_path = os.path.join(os.path.dirname(__file__), 'data', 'skills_database.json')
    try:
        with open(onet_path, 'r') as f:
            roles = json.load(f).get('roles', {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    skill_category_counts = {}
    for role_data in roles.values():
        category = role_data.get('category', 'General')
        for skill in role_data.get('required_skills', []) + role_data.get('preferred_skills', []):
            skill_category_counts.setdefault(skill, {})
            skill_category_counts[skill][category] = skill_category_counts[skill].get(category, 0) + 1

    # assign each skill to its most frequent category
    return {
        skill: max(cats, key=cats.get)
        for skill, cats in skill_category_counts.items()
    }


def _generate_roadmap_fallback(missing_skills, target_role, persona):
    """Build a roadmap from our curated resources file + generated search URLs.Groups skills by topic
    """
    resources_path = os.path.join(os.path.dirname(__file__), 'data', 'resources.json')
    try:
        with open(resources_path, 'r') as f:
            all_resources = json.load(f).get('skills', {})
    except (FileNotFoundError, json.JSONDecodeError):
        all_resources = {}

    skill_names = [
        s.get('skill', s) if isinstance(s, dict) else s
        for s in missing_skills[:15]
    ]

    # group skills by their topic category from fallback data
    topic_map = _load_skill_topic_map()
    topic_groups = {}
    for skill in skill_names:
        topic = topic_map.get(skill, 'General')
        topic_groups.setdefault(topic, []).append(skill)

    # order groups: larger groups first so more skills have a higher demand cluster
    ordered_groups = sorted(topic_groups.items(), key=lambda x: -len(x[1]))

    phases = []
    phase_num = 1

    for topic, batch in ordered_groups:
        free_resources = []
        paid_resources = []

        for skill in batch:
            skill_resources = all_resources.get(skill, {})

            if skill_resources:
                free_resources.extend(skill_resources.get('free', [])[:2])
                paid_resources.extend(skill_resources.get('paid', [])[:1])
            else:
                encoded = skill.replace(' ', '+')
                free_resources.append({
                    'title': f'Search: Learn {skill}',
                    'platform': 'YouTube',
                    'url': f'https://www.youtube.com/results?search_query=learn+{encoded}+beginners',
                    'est_hours': 5,
                    'type': 'video',
                })
                free_resources.append({
                    'title': f'Search: {skill} courses',
                    'platform': 'freeCodeCamp / Coursera (free audit)',
                    'url': f'https://www.coursera.org/search?query={encoded}',
                    'est_hours': 10,
                    'type': 'course',
                })
                paid_resources.append({
                    'title': f'Search: {skill} courses',
                    'platform': 'Udemy',
                    'url': f'https://www.udemy.com/courses/search/?q={encoded}',
                    'est_hours': 15,
                    'price_range': '$10-20',
                    'type': 'course',
                })

        # sort resources by shortest time first
        free_resources.sort(key=lambda r: r.get('est_hours', 0))
        paid_resources.sort(key=lambda r: r.get('est_hours', 0))

        weeks = len(batch) * 2
        phases.append({
            'phase_name': f'Phase {phase_num}: {topic}',
            'duration': f'{weeks}-{weeks + 2} weeks',
            'skills': batch,
            'free_resources': free_resources,
            'paid_resources': paid_resources,
        })
        phase_num += 1

    total_weeks = sum(len(p['skills']) * 2 for p in phases)
    total_months = max(1, total_weeks // 4)

    return {
        'phases': phases,
        'total_estimated_time': f'{total_months}-{total_months + 2} months',
        'certifications_recommended': [],
        'method': 'fallback',
    }